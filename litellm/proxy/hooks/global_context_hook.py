# +------------------------------------+
#
#        Global Context / System Prompt Hook
#
# +------------------------------------+
# Prepend a configurable system prompt/context to all chat completion requests.
# The context can be configured from the UI or via API.

from typing import Any, Dict, List, Literal, Optional, cast

from litellm._logging import verbose_proxy_logger
from litellm.caching.caching import DualCache
from litellm.integrations.custom_logger import CustomLogger
from litellm.proxy._types import UserAPIKeyAuth
from litellm.types.llms.openai import AllMessageValues


class GlobalContextHook(CustomLogger):
    """
    Hook to prepend a global system prompt/context to all chat completion requests.
    
    This allows administrators to set a default context that will be included
    in all requests going through the proxy.
    """

    def __init__(self):
        self.global_context: Optional[str] = None
        super().__init__()

    def print_verbose(self, print_statement, level: Literal["INFO", "DEBUG"] = "DEBUG"):
        if level == "INFO":
            verbose_proxy_logger.info(print_statement)
        elif level == "DEBUG":
            verbose_proxy_logger.debug(print_statement)

    def set_global_context(self, context: Optional[str]):
        """
        Set the global context/system prompt.
        
        Args:
            context: The system prompt to prepend to all requests. Set to None to disable.
        """
        self.global_context = context
        self.print_verbose(
            f"Global context updated: {context[:100] if context else 'None'}...",
            level="INFO"
        )

    def get_global_context(self) -> Optional[str]:
        """
        Get the current global context/system prompt.
        
        Returns:
            The current global context or None if not set.
        """
        return self.global_context

    def _prepend_system_message(
        self, 
        messages: List[Any], 
        system_content: str
    ) -> List[Any]:
        """
        Prepend a system message to the messages list.
        
        If the first message is already a system message, prepend the global context
        to its content. Otherwise, insert a new system message at the beginning.
        
        Args:
            messages: The original list of messages
            system_content: The system prompt content to prepend
            
        Returns:
            The modified messages list with the system prompt prepended
        """
        if not messages:
            return [{"role": "system", "content": system_content}]
        
        # Check if first message is a system message
        first_message = messages[0]
        if isinstance(first_message, dict) and first_message.get("role") == "system":
            # Prepend to existing system message
            existing_content = first_message.get("content", "")
            if isinstance(existing_content, str):
                combined_content = f"{system_content}\n\n{existing_content}"
            else:
                # Handle case where content might be a list (multimodal)
                combined_content = f"{system_content}\n\n{str(existing_content)}"
            
            modified_messages: List[Any] = list(messages)
            modified_messages[0] = {
                **first_message,
                "content": combined_content
            }
            return modified_messages
        else:
            # Insert new system message at the beginning
            system_message: Dict[str, str] = {"role": "system", "content": system_content}
            return [system_message] + list(messages)

    async def async_pre_call_hook(
        self,
        user_api_key_dict: UserAPIKeyAuth,
        cache: DualCache,
        data: dict,
        call_type: str,
    ) -> dict:
        """
        Called before making an LLM API call.
        
        Prepends the global context to the messages if:
        - Global context is set
        - The call type is a chat completion
        - Messages are present in the request
        
        Args:
            user_api_key_dict: Information about the API key making the request
            cache: The proxy cache
            data: The request data
            call_type: The type of call (completion, embeddings, etc.)
            
        Returns:
            The potentially modified request data
        """
        try:
            self.print_verbose(
                f"GlobalContextHook: Processing {call_type} request"
            )
            
            # Only process chat completion requests
            if call_type not in ["acompletion", "completion"]:
                return data
            
            # Check if global context is set
            if not self.global_context:
                self.print_verbose("GlobalContextHook: No global context set, skipping")
                return data
            
            # Check if messages are present
            messages = data.get("messages")
            if not messages or not isinstance(messages, list):
                self.print_verbose("GlobalContextHook: No messages in request, skipping")
                return data
            
            # Check if the request explicitly opts out of global context
            metadata = data.get("metadata", {}) or {}
            if metadata.get("skip_global_context") is True:
                self.print_verbose("GlobalContextHook: Request opted out, skipping")
                return data
            
            # Prepend the global context
            self.print_verbose(
                f"GlobalContextHook: Prepending global context to {len(messages)} messages"
            )
            data["messages"] = self._prepend_system_message(
                messages, 
                self.global_context
            )
            
            return data

        except Exception as e:
            verbose_proxy_logger.exception(
                f"GlobalContextHook: Exception occurred - {str(e)}"
            )
            # Don't block the request on error, just log and return original data
            return data


# Singleton instance for the global context hook
global_context_hook = GlobalContextHook()
