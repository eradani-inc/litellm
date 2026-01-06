"""
API Endpoints for managing Global Context / System Prompt

These endpoints allow administrators to configure a global system prompt
that will be prepended to all chat completion requests going through the proxy.
"""

from typing import TYPE_CHECKING, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from litellm._logging import verbose_proxy_logger
from litellm.proxy._types import LitellmUserRoles, UserAPIKeyAuth
from litellm.proxy.auth.user_api_key_auth import user_api_key_auth

if TYPE_CHECKING:
    from litellm.proxy.hooks.global_context_hook import GlobalContextHook

router = APIRouter()


class GlobalContextRequest(BaseModel):
    """Request model for setting global context"""
    global_context: Optional[str] = Field(
        None, 
        description="The system prompt/context to prepend to all chat completion requests. Set to null or empty string to disable."
    )


class GlobalContextResponse(BaseModel):
    """Response model for global context operations"""
    success: bool
    message: str
    global_context: Optional[str] = None


def _get_global_context_hook() -> "GlobalContextHook":
    """
    Get the global context hook instance from proxy_logging_obj.
    
    Returns the hook instance or raises an error if not available.
    """
    from litellm.proxy.proxy_server import proxy_logging_obj
    
    if proxy_logging_obj is None:
        raise HTTPException(
            status_code=503,
            detail="Proxy logging not initialized"
        )
    
    hook = proxy_logging_obj.get_proxy_hook("global_context")
    if hook is None:
        raise HTTPException(
            status_code=503,
            detail="Global context hook not initialized. Restart the proxy server."
        )
    
    from litellm.proxy.hooks.global_context_hook import GlobalContextHook
    if not isinstance(hook, GlobalContextHook):
        raise HTTPException(
            status_code=503,
            detail="Invalid global context hook type"
        )
    
    return hook


@router.get(
    "/config/global_context",
    tags=["Global Context Settings"],
    dependencies=[Depends(user_api_key_auth)],
    response_model=GlobalContextResponse,
)
async def get_global_context(
    user_api_key_dict: UserAPIKeyAuth = Depends(user_api_key_auth),
) -> GlobalContextResponse:
    """
    Get the current global context/system prompt.
    
    This is the system prompt that gets prepended to all chat completion requests.
    
    👉 [Global Context Docs](https://docs.litellm.ai/docs/proxy/global_context)
    
    Example Request:
    ```bash
    curl -X GET "http://localhost:4000/config/global_context" \\
        -H "Authorization: Bearer <your_api_key>"
    ```
    
    Example Response:
    ```json
    {
        "success": true,
        "message": "Global context retrieved successfully",
        "global_context": "You are a helpful AI assistant for Acme Corp..."
    }
    ```
    """
    try:
        global_context_hook = _get_global_context_hook()
        current_context = global_context_hook.get_global_context()
        
        return GlobalContextResponse(
            success=True,
            message="Global context retrieved successfully" if current_context else "No global context configured",
            global_context=current_context
        )
    except HTTPException:
        raise
    except Exception as e:
        verbose_proxy_logger.exception(f"Error getting global context: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Error getting global context: {str(e)}"
        )


@router.post(
    "/config/global_context",
    tags=["Global Context Settings"],
    dependencies=[Depends(user_api_key_auth)],
    response_model=GlobalContextResponse,
)
async def set_global_context(
    request: GlobalContextRequest,
    user_api_key_dict: UserAPIKeyAuth = Depends(user_api_key_auth),
) -> GlobalContextResponse:
    """
    Set the global context/system prompt.
    
    This system prompt will be prepended to all chat completion requests
    going through the proxy. Only proxy admins can set this.
    
    👉 [Global Context Docs](https://docs.litellm.ai/docs/proxy/global_context)
    
    Example Request:
    ```bash
    curl -X POST "http://localhost:4000/config/global_context" \\
        -H "Authorization: Bearer <your_api_key>" \\
        -H "Content-Type: application/json" \\
        -d '{
            "global_context": "You are a helpful AI assistant for Acme Corp. Always be polite and professional."
        }'
    ```
    
    Example Response:
    ```json
    {
        "success": true,
        "message": "Global context updated successfully",
        "global_context": "You are a helpful AI assistant for Acme Corp..."
    }
    ```
    
    To disable global context, send null or empty string:
    ```bash
    curl -X POST "http://localhost:4000/config/global_context" \\
        -H "Authorization: Bearer <your_api_key>" \\
        -H "Content-Type: application/json" \\
        -d '{"global_context": null}'
    ```
    """
    from litellm.proxy.proxy_server import prisma_client
    
    # Only allow proxy admins to set global context
    if user_api_key_dict.user_role is None or (
        user_api_key_dict.user_role != LitellmUserRoles.PROXY_ADMIN
        and user_api_key_dict.user_role != LitellmUserRoles.PROXY_ADMIN.value
    ):
        raise HTTPException(
            status_code=403, 
            detail="Only proxy admins can set global context"
        )
    
    try:
        global_context_hook = _get_global_context_hook()
        
        # Normalize empty string to None
        new_context = request.global_context
        if new_context is not None and new_context.strip() == "":
            new_context = None
        
        # Update the hook
        global_context_hook.set_global_context(new_context)
        
        # Persist to database if available
        if prisma_client is not None:
            try:
                import json
                await prisma_client.db.litellm_config.upsert(
                    where={"param_name": "global_context"},
                    data={
                        "create": {
                            "param_name": "global_context",
                            "param_value": json.dumps({"global_context": new_context}),
                        },
                        "update": {
                            "param_value": json.dumps({"global_context": new_context}),
                        },
                    },
                )
                verbose_proxy_logger.info("Global context persisted to database")
            except Exception as db_error:
                verbose_proxy_logger.warning(
                    f"Failed to persist global context to database: {db_error}. "
                    "Context will be reset on proxy restart."
                )
        
        if new_context:
            return GlobalContextResponse(
                success=True,
                message="Global context updated successfully",
                global_context=new_context
            )
        else:
            return GlobalContextResponse(
                success=True,
                message="Global context disabled",
                global_context=None
            )
            
    except HTTPException:
        raise
    except Exception as e:
        verbose_proxy_logger.exception(f"Error setting global context: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Error setting global context: {str(e)}"
        )


@router.delete(
    "/config/global_context",
    tags=["Global Context Settings"],
    dependencies=[Depends(user_api_key_auth)],
    response_model=GlobalContextResponse,
)
async def delete_global_context(
    user_api_key_dict: UserAPIKeyAuth = Depends(user_api_key_auth),
) -> GlobalContextResponse:
    """
    Delete/disable the global context/system prompt.
    
    This will remove the global system prompt so it's no longer prepended
    to chat completion requests. Only proxy admins can delete this.
    
    👉 [Global Context Docs](https://docs.litellm.ai/docs/proxy/global_context)
    
    Example Request:
    ```bash
    curl -X DELETE "http://localhost:4000/config/global_context" \\
        -H "Authorization: Bearer <your_api_key>"
    ```
    
    Example Response:
    ```json
    {
        "success": true,
        "message": "Global context deleted successfully",
        "global_context": null
    }
    ```
    """
    from litellm.proxy.proxy_server import prisma_client
    
    # Only allow proxy admins to delete global context
    if user_api_key_dict.user_role is None or (
        user_api_key_dict.user_role != LitellmUserRoles.PROXY_ADMIN
        and user_api_key_dict.user_role != LitellmUserRoles.PROXY_ADMIN.value
    ):
        raise HTTPException(
            status_code=403, 
            detail="Only proxy admins can delete global context"
        )
    
    try:
        global_context_hook = _get_global_context_hook()
        
        # Clear the hook
        global_context_hook.set_global_context(None)
        
        # Remove from database if available
        if prisma_client is not None:
            try:
                await prisma_client.db.litellm_config.delete(
                    where={"param_name": "global_context"}
                )
                verbose_proxy_logger.info("Global context deleted from database")
            except Exception as db_error:
                # It's okay if the record doesn't exist
                verbose_proxy_logger.debug(
                    f"Could not delete global context from database: {db_error}"
                )
        
        return GlobalContextResponse(
            success=True,
            message="Global context deleted successfully",
            global_context=None
        )
            
    except HTTPException:
        raise
    except Exception as e:
        verbose_proxy_logger.exception(f"Error deleting global context: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Error deleting global context: {str(e)}"
        )


async def load_global_context_from_db():
    """
    Load global context from database on proxy startup.
    
    This should be called during proxy initialization.
    """
    from litellm.proxy.proxy_server import prisma_client, proxy_logging_obj
    
    if prisma_client is None:
        verbose_proxy_logger.debug("No database client, skipping global context load")
        return
    
    if proxy_logging_obj is None:
        verbose_proxy_logger.debug("Proxy logging not initialized, skipping global context load")
        return
    
    try:
        import json
        config = await prisma_client.db.litellm_config.find_unique(
            where={"param_name": "global_context"}
        )
        
        if config and config.param_value:
            data = json.loads(config.param_value)
            context = data.get("global_context")
            if context:
                from litellm.proxy.hooks.global_context_hook import GlobalContextHook
                global_context_hook = proxy_logging_obj.get_proxy_hook("global_context")
                if global_context_hook and isinstance(global_context_hook, GlobalContextHook):
                    global_context_hook.set_global_context(context)
                    verbose_proxy_logger.info("Loaded global context from database")
    except Exception as e:
        verbose_proxy_logger.warning(f"Failed to load global context from database: {e}")
