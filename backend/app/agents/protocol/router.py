"""Message router for agent communication.

This module provides routing capabilities for agent messages,
ensuring messages reach the appropriate agents.
"""
import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set

from app.agents.base import AgentType, BaseAgent
from app.agents.protocol.message import (
    AgentMessage,
    AgentMessageType,
    AgentRequest,
    AgentResponse,
    BroadcastMessage,
    MessagePriority,
    MessageStatus,
    RequestType,
    ResponseStatus,
)

logger = logging.getLogger(__name__)


class RoutingAction(str, Enum):
    """Actions the router can take for a message."""

    DELIVER = "deliver"
    QUEUE = "queue"
    REJECT = "reject"
    DEFER = "defer"
    BROADCAST = "broadcast"


@dataclass
class RoutingRule:
    """Rule for routing messages.

    Rules can be used to customize message routing behavior
    based on various criteria.
    """

    name: str
    condition: Callable[[AgentMessage], bool]
    action: RoutingAction
    target: Optional[AgentType] = None
    priority: int = 100  # Lower number = higher priority
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class MessageRoute:
    """Represents a route for a message."""

    message_id: str
    source: AgentType
    targets: List[AgentType]
    action: RoutingAction
    queued_at: datetime = field(default_factory=datetime.utcnow)
    delivered_at: Optional[datetime] = None
    status: MessageStatus = MessageStatus.PENDING
    error: Optional[str] = None


class AgentRouter:
    """Router for agent messages.

    The router is responsible for:
    1. Delivering messages to appropriate agents
    2. Managing message queues per agent
    3. Applying routing rules
    4. Tracking message delivery status
    """

    def __init__(self) -> None:
        """Initialize the router."""
        self._agents: Dict[AgentType, BaseAgent] = {}
        self._queues: Dict[AgentType, asyncio.Queue] = {}
        self._pending_responses: Dict[str, asyncio.Future] = {}
        self._routes: Dict[str, MessageRoute] = {}
        self._rules: List[RoutingRule] = []
        self._running = False
        self._worker_tasks: List[asyncio.Task] = []

        # Default request type to agent type mapping
        self._request_mapping: Dict[RequestType, AgentType] = {
            RequestType.ARCHITECT_REVIEW: AgentType.ARCHITECT,
            RequestType.ARCHITECT_VALIDATE: AgentType.ARCHITECT,
            RequestType.ARCHITECT_ANALYZE: AgentType.ARCHITECT,
            RequestType.BACKEND_GENERATE: AgentType.BACKEND,
            RequestType.BACKEND_MODIFY: AgentType.BACKEND,
            RequestType.BACKEND_VALIDATE: AgentType.BACKEND,
            RequestType.FRONTEND_GENERATE: AgentType.FRONTEND,
            RequestType.FRONTEND_MODIFY: AgentType.FRONTEND,
            RequestType.FRONTEND_VALIDATE: AgentType.FRONTEND,
            RequestType.DATA_MIGRATION: AgentType.DATA,
            RequestType.DATA_SCHEMA: AgentType.DATA,
            RequestType.DATA_VALIDATE: AgentType.DATA,
            RequestType.PM_CLARIFY: AgentType.PM,
            RequestType.PM_DISPATCH: AgentType.PM,
            RequestType.PM_REPORT: AgentType.PM,
        }

    def register_agent(self, agent: BaseAgent) -> None:
        """Register an agent with the router.

        Args:
            agent: The agent instance to register
        """
        self._agents[agent.agent_type] = agent
        if agent.agent_type not in self._queues:
            self._queues[agent.agent_type] = asyncio.Queue()
        logger.info(f"Registered agent: {agent.name} ({agent.agent_type.value})")

    def unregister_agent(self, agent_type: AgentType) -> None:
        """Unregister an agent from the router.

        Args:
            agent_type: The type of agent to unregister
        """
        if agent_type in self._agents:
            del self._agents[agent_type]
            logger.info(f"Unregistered agent: {agent_type.value}")

    def add_rule(self, rule: RoutingRule) -> None:
        """Add a routing rule.

        Rules are evaluated in priority order (lowest number first).

        Args:
            rule: The routing rule to add
        """
        self._rules.append(rule)
        self._rules.sort(key=lambda r: r.priority)
        logger.info(f"Added routing rule: {rule.name}")

    def remove_rule(self, name: str) -> bool:
        """Remove a routing rule by name.

        Args:
            name: Name of the rule to remove

        Returns:
            True if rule was found and removed
        """
        for i, rule in enumerate(self._rules):
            if rule.name == name:
                del self._rules[i]
                logger.info(f"Removed routing rule: {name}")
                return True
        return False

    async def start(self) -> None:
        """Start the router workers."""
        if self._running:
            return

        self._running = True
        # Start a worker for each agent queue
        for agent_type in self._queues:
            task = asyncio.create_task(self._process_queue(agent_type))
            self._worker_tasks.append(task)

        logger.info("Agent router started")

    async def stop(self) -> None:
        """Stop the router workers."""
        self._running = False

        # Cancel all workers
        for task in self._worker_tasks:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

        self._worker_tasks.clear()
        logger.info("Agent router stopped")

    async def route(self, message: AgentMessage) -> MessageRoute:
        """Route a message to appropriate agent(s).

        Args:
            message: The message to route

        Returns:
            MessageRoute indicating routing status
        """
        # Apply routing rules
        action, target = self._apply_rules(message)

        # Determine targets
        targets = self._determine_targets(message, action, target)

        # Create route record
        route = MessageRoute(
            message_id=message.message_id,
            source=message.sender,
            targets=targets,
            action=action,
        )
        self._routes[message.message_id] = route

        if action == RoutingAction.REJECT:
            route.status = MessageStatus.FAILED
            route.error = "Message rejected by routing rules"
            return route

        if action == RoutingAction.DEFER:
            route.status = MessageStatus.PENDING
            return route

        # Deliver message
        if isinstance(message, BroadcastMessage):
            await self._deliver_broadcast(message, targets)
        else:
            await self._deliver_to_targets(message, targets)

        route.delivered_at = datetime.utcnow()
        route.status = MessageStatus.DELIVERED

        return route

    async def send_request(
        self,
        request: AgentRequest,
        timeout: Optional[float] = None,
    ) -> AgentResponse:
        """Send a request and wait for response.

        Args:
            request: The request to send
            timeout: Timeout in seconds (uses request.timeout_seconds if not set)

        Returns:
            AgentResponse from the target agent

        Raises:
            asyncio.TimeoutError: If no response within timeout
        """
        timeout = timeout or request.timeout_seconds

        # Create future for response
        future: asyncio.Future = asyncio.get_event_loop().create_future()
        self._pending_responses[request.message_id] = future

        try:
            # Route the request
            await self.route(request)

            # Wait for response
            response = await asyncio.wait_for(future, timeout=timeout)
            return response

        except asyncio.TimeoutError:
            logger.warning(f"Request {request.message_id} timed out")
            raise

        finally:
            self._pending_responses.pop(request.message_id, None)

    async def handle_response(self, response: AgentResponse) -> None:
        """Handle an incoming response.

        Args:
            response: The response to handle
        """
        correlation_id = response.correlation_id
        if correlation_id and correlation_id in self._pending_responses:
            future = self._pending_responses[correlation_id]
            if not future.done():
                future.set_result(response)

    def get_route_status(self, message_id: str) -> Optional[MessageRoute]:
        """Get the routing status of a message.

        Args:
            message_id: The message ID to check

        Returns:
            MessageRoute if found, None otherwise
        """
        return self._routes.get(message_id)

    def get_queue_size(self, agent_type: AgentType) -> int:
        """Get the number of pending messages for an agent.

        Args:
            agent_type: The agent type to check

        Returns:
            Number of pending messages
        """
        queue = self._queues.get(agent_type)
        return queue.qsize() if queue else 0

    def _apply_rules(
        self,
        message: AgentMessage,
    ) -> tuple[RoutingAction, Optional[AgentType]]:
        """Apply routing rules to determine action.

        Args:
            message: The message to evaluate

        Returns:
            Tuple of (action, optional target override)
        """
        for rule in self._rules:
            if rule.condition(message):
                logger.debug(f"Rule '{rule.name}' matched for message {message.message_id}")
                return rule.action, rule.target

        # Default action
        return RoutingAction.DELIVER, None

    def _determine_targets(
        self,
        message: AgentMessage,
        action: RoutingAction,
        target_override: Optional[AgentType],
    ) -> List[AgentType]:
        """Determine target agents for a message.

        Args:
            message: The message
            action: The routing action
            target_override: Optional target from rules

        Returns:
            List of target agent types
        """
        if target_override:
            return [target_override]

        if isinstance(message, BroadcastMessage):
            return message.target_agents

        if isinstance(message, AgentRequest):
            # Map request type to agent
            target = self._request_mapping.get(message.request_type)
            if target:
                return [target]

        # Use explicit receiver
        if message.receiver:
            return [message.receiver]

        return []

    async def _deliver_broadcast(
        self,
        message: BroadcastMessage,
        targets: List[AgentType],
    ) -> None:
        """Deliver a broadcast message to multiple targets.

        Args:
            message: The broadcast message
            targets: List of target agent types
        """
        for target in targets:
            if target in self._queues:
                await self._queues[target].put(message)
                logger.debug(f"Queued broadcast {message.message_id} for {target.value}")

    async def _deliver_to_targets(
        self,
        message: AgentMessage,
        targets: List[AgentType],
    ) -> None:
        """Deliver a message to specific targets.

        Args:
            message: The message
            targets: List of target agent types
        """
        for target in targets:
            if target in self._queues:
                await self._queues[target].put(message)
                logger.debug(f"Queued message {message.message_id} for {target.value}")
            else:
                logger.warning(f"No queue for agent type: {target.value}")

    async def _process_queue(self, agent_type: AgentType) -> None:
        """Process messages from an agent's queue.

        Args:
            agent_type: The agent type whose queue to process
        """
        queue = self._queues[agent_type]
        agent = self._agents.get(agent_type)

        if not agent:
            logger.warning(f"No agent registered for type: {agent_type.value}")
            return

        while self._running:
            try:
                # Get message from queue
                message = await asyncio.wait_for(queue.get(), timeout=1.0)

                # Process based on message type
                if isinstance(message, AgentResponse):
                    await self.handle_response(message)
                elif isinstance(message, AgentRequest):
                    response = await self._handle_request(agent, message)
                    if response:
                        await self.route(response)

            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error processing message for {agent_type.value}: {e}")

    async def _handle_request(
        self,
        agent: BaseAgent,
        request: AgentRequest,
    ) -> Optional[AgentResponse]:
        """Handle a request by routing to agent.

        Args:
            agent: The agent to handle the request
            request: The request to handle

        Returns:
            Response if applicable, None otherwise
        """
        try:
            # Process through agent
            if request.context and request.context.task_card:
                # Execute task card if available
                result = await agent.execute(request.context.task_card)
                return AgentResponse.success(request, result)
            else:
                # Process as message
                result = await agent.process_message(
                    session_id=request.context.session_id if request.context else "",
                    message=str(request.payload),
                    context=request.payload,
                )
                return AgentResponse.success(request, result)

        except Exception as e:
            logger.error(f"Agent {agent.name} failed to handle request: {e}")
            return AgentResponse.failure(request, str(e))


# Global router instance
_router: Optional[AgentRouter] = None


def get_router() -> AgentRouter:
    """Get or create the global router instance."""
    global _router
    if _router is None:
        _router = AgentRouter()
    return _router


async def start_router() -> None:
    """Start the global router."""
    router = get_router()
    await router.start()


async def stop_router() -> None:
    """Stop the global router."""
    global _router
    if _router:
        await _router.stop()