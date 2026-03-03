import importlib
import os
import sys
from collections.abc import Sequence
from enum import Enum
from typing import Annotated, Any, Callable, Literal, Optional, Union

from annotated_doc import Doc
from fastapi import FastAPI, params
from fastapi.datastructures import Default
from fastapi.routing import APIRoute, APIRouter
from fastapi.utils import generate_unique_id
from starlette.responses import JSONResponse, Response
from starlette.routing import BaseRoute
from starlette.types import ASGIApp, Lifespan
from typing_extensions import deprecated

from utils.log_util import logger


class APIRouterPro(APIRouter):
    """
    `APIRouterPro` class, inherited from the `APIRouter` class, it has all the functions of `APIRouter` and provides some additional parameter settings.
    `APIRouter` class, used to group *path operations*, for example to structure
    an app in multiple files. It would then be included in the `FastAPI` app, or
    in another `APIRouter` (ultimately included in the app).

    Read more about it in the
    [FastAPI docs for Bigger Applications - Multiple Files](https://fastapi.tiangolo.com/tutorial/bigger-applications/).

    ## Example

    ```python
    from common.router import APIRouterPro, FastAPI

    app = FastAPI()
    router = APIRouterPro()


    @router.get('/users/', tags=['users'])
    async def read_users():
        return [{'username': 'Rick'}, {'username': 'Morty'}]


    app.include_router(router)
    ```
    """

    def __init__(  # noqa: PLR0913
        self,
        *,
        prefix: Annotated[str, Doc('An optional path prefix for the router.')] = '',
        order_num: Annotated[int, Doc('An optional order number for the router.')] = 100,
        auto_register: Annotated[bool, Doc('An optional auto register flag for the router.')] = True,
        tags: Annotated[
            Optional[list[Union[str, Enum]]],
            Doc(
                """
                A list of tags to be applied to all the *path operations* in this
                router.

                It will be added to the generated OpenAPI (e.g. visible at `/docs`).

                Read more about it in the
                [FastAPI docs for Path Operation Configuration](https://fastapi.tiangolo.com/tutorial/path-operation-configuration/).
                """
            ),
        ] = None,
        dependencies: Annotated[
            Optional[Sequence[params.Depends]],
            Doc(
                """
                A list of dependencies (using `Depends()`) to be applied to all the
                *path operations* in this router.

                Read more about it in the
                [FastAPI docs for Bigger Applications - Multiple Files](https://fastapi.tiangolo.com/tutorial/bigger-applications/#include-an-apirouter-with-a-custom-prefix-tags-responses-and-dependencies).
                """
            ),
        ] = None,
        default_response_class: Annotated[
            type[Response],
            Doc(
                """
                The default response class to be used.

                Read more in the
                [FastAPI docs for Custom Response - HTML, Stream, File, others](https://fastapi.tiangolo.com/advanced/custom-response/#default-response-class).
                """
            ),
        ] = Default(JSONResponse),
        responses: Annotated[
            Optional[dict[Union[int, str], dict[str, Any]]],
            Doc(
                """
                Additional responses to be shown in OpenAPI.

                It will be added to the generated OpenAPI (e.g. visible at `/docs`).

                Read more about it in the
                [FastAPI docs for Additional Responses in OpenAPI](https://fastapi.tiangolo.com/advanced/additional-responses/).

                And in the
                [FastAPI docs for Bigger Applications](https://fastapi.tiangolo.com/tutorial/bigger-applications/#include-an-apirouter-with-a-custom-prefix-tags-responses-and-dependencies).
                """
            ),
        ] = None,
        callbacks: Annotated[
            Optional[list[BaseRoute]],
            Doc(
                """
                OpenAPI callbacks that should apply to all *path operations* in this
                router.

                It will be added to the generated OpenAPI (e.g. visible at `/docs`).

                Read more about it in the
                [FastAPI docs for OpenAPI Callbacks](https://fastapi.tiangolo.com/advanced/openapi-callbacks/).
                """
            ),
        ] = None,
        routes: Annotated[
            Optional[list[BaseRoute]],
            Doc(
                """
                **Note**: you probably shouldn't use this parameter, it is inherited
                from Starlette and supported for compatibility.

                ---

                A list of routes to serve incoming HTTP and WebSocket requests.
                """
            ),
            deprecated(
                """
                You normally wouldn't use this parameter with FastAPI, it is inherited
                from Starlette and supported for compatibility.

                In FastAPI, you normally would use the *path operation methods*,
                like `router.get()`, `router.post()`, etc.
                """
            ),
        ] = None,
        redirect_slashes: Annotated[
            bool,
            Doc(
                """
                Whether to detect and redirect slashes in URLs when the client doesn't
                use the same format.
                """
            ),
        ] = True,
        default: Annotated[
            Optional[ASGIApp],
            Doc(
                """
                Default function handler for this router. Used to handle
                404 Not Found errors.
                """
            ),
        ] = None,
        dependency_overrides_provider: Annotated[
            Optional[Any],
            Doc(
                """
                Only used internally by FastAPI to handle dependency overrides.

                You shouldn't need to use it. It normally points to the `FastAPI` app
                object.
                """
            ),
        ] = None,
        route_class: Annotated[
            type[APIRoute],
            Doc(
                """
                Custom route (*path operation*) class to be used by this router.

                Read more about it in the
                [FastAPI docs for Custom Request and APIRoute class](https://fastapi.tiangolo.com/how-to/custom-request-and-route/#custom-apiroute-class-in-a-router).
                """
            ),
        ] = APIRoute,
        on_startup: Annotated[
            Optional[Sequence[Callable[[], Any]]],
            Doc(
                """
                A list of startup event handler functions.

                You should instead use the `lifespan` handlers.

                Read more in the [FastAPI docs for `lifespan`](https://fastapi.tiangolo.com/advanced/events/).
                """
            ),
        ] = None,
        on_shutdown: Annotated[
            Optional[Sequence[Callable[[], Any]]],
            Doc(
                """
                A list of shutdown event handler functions.

                You should instead use the `lifespan` handlers.

                Read more in the
                [FastAPI docs for `lifespan`](https://fastapi.tiangolo.com/advanced/events/).
                """
            ),
        ] = None,
        # the generic to Lifespan[AppType] is the type of the top level application
        # which the router cannot know statically, so we use typing.Any
        lifespan: Annotated[
            Optional[Lifespan[Any]],
            Doc(
                """
                A `Lifespan` context manager handler. This replaces `startup` and
                `shutdown` functions with a single context manager.

                Read more in the
                [FastAPI docs for `lifespan`](https://fastapi.tiangolo.com/advanced/events/).
                """
            ),
        ] = None,
        deprecated: Annotated[
            Optional[bool],
            Doc(
                """
                Mark all *path operations* in this router as deprecated.

                It will be added to the generated OpenAPI (e.g. visible at `/docs`).

                Read more about it in the
                [FastAPI docs for Path Operation Configuration](https://fastapi.tiangolo.com/tutorial/path-operation-configuration/).
                """
            ),
        ] = None,
        include_in_schema: Annotated[
            bool,
            Doc(
                """
                To include (or not) all the *path operations* in this router in the
                generated OpenAPI.

                This affects the generated OpenAPI (e.g. visible at `/docs`).

                Read more about it in the
                [FastAPI docs for Query Parameters and String Validations](https://fastapi.tiangolo.com/tutorial/query-params-str-validations/#exclude-parameters-from-openapi).
                """
            ),
        ] = True,
        generate_unique_id_function: Annotated[
            Callable[[APIRoute], str],
            Doc(
                """
                Customize the function used to generate unique IDs for the *path
                operations* shown in the generated OpenAPI.

                This is particularly useful when automatically generating clients or
                SDKs for your API.

                Read more about it in the
                [FastAPI docs about how to Generate Clients](https://fastapi.tiangolo.com/advanced/generate-clients/#custom-generate-unique-id-function).
                """
            ),
        ] = Default(generate_unique_id),
    ) -> None:
        self.order_num = order_num
        self.auto_register = auto_register
        super().__init__(
            prefix=prefix,
            tags=tags,
            dependencies=dependencies,
            default_response_class=default_response_class,
            responses=responses,
            callbacks=callbacks,
            routes=routes,
            redirect_slashes=redirect_slashes,
            default=default,
            dependency_overrides_provider=dependency_overrides_provider,
            route_class=route_class,
            on_startup=on_startup,
            on_shutdown=on_shutdown,
            lifespan=lifespan,
            deprecated=deprecated,
            include_in_schema=include_in_schema,
            generate_unique_id_function=generate_unique_id_function,
        )


class RouterRegister:
    """
    璺敱娉ㄥ唽鍣紝鐢ㄤ簬鑷姩娉ㄥ唽鎵€鏈塩ontroller鐩綍涓嬬殑璺敱
    """

    def __init__(self, app: FastAPI) -> None:
        """
        鍒濆鍖栬矾鐢辨敞鍐屽櫒

        :param app: FastAPI瀵硅薄
        """
        self.app = app
        self.project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
        sys.path.insert(0, self.project_root)

    def _find_controller_files(self) -> list[str]:
        """
        鏌ユ壘鎵€鏈塩ontroller鍜宎pi鐩綍涓嬬殑py鏂囦欢

        :return: py鏂囦欢璺緞鍒楄〃
        """
        controller_files = []
        # 閬嶅巻鎵€鏈夌洰褰曪紝鏌ユ壘controller鍜宎pi鐩綍
        for root, _dirs, files in os.walk(self.project_root):
            # 妫€鏌ュ綋鍓嶇洰褰曟槸鍚︿负controller鎴朼pi鐩綍
            dir_name = os.path.basename(root)
            if dir_name in ('controller', 'api'):
                # 閬嶅巻鐩綍涓嬬殑鎵€鏈塸y鏂囦欢
                for file in files:
                    if file.endswith('.py') and not file.startswith('__'):
                        file_path = os.path.join(root, file)
                        controller_files.append(file_path)
        return controller_files

    def _import_module_and_get_routers(
        self, controller_files: list[str]
    ) -> tuple[list[tuple[str, APIRouter]], list[tuple[str, str]]]:
        """
        瀵煎叆妯″潡骞惰幏鍙栬矾鐢卞疄渚?
        :param controller_files: controller鐩綍涓嬬殑py鏂囦欢璺緞鍒楄〃
        :return: 璺敱瀹炰緥鍒楄〃
        """
        routers = []
        import_failures = []
        for file_path in controller_files:
            # 璁＄畻妯″潡璺緞
            relative_path = os.path.relpath(file_path, self.project_root)
            module_name = relative_path.replace(os.sep, '.')[:-3]

            try:
                module = importlib.import_module(module_name)
                # 閬嶅巻妯″潡灞炴€э紝瀵绘壘APIRouter鍜孉PIRouterPro瀹炰緥
                for attr_name in dir(module):
                    attr = getattr(module, attr_name)
                    # 瀵逛簬APIRouterPro瀹炰緥锛屽彧鏈夊綋auto_register=True鏃舵墠娣诲姞
                    if isinstance(attr, APIRouterPro):
                        if attr.auto_register:
                            routers.append((attr_name, attr))
                    # 瀵逛簬APIRouter瀹炰緥锛岀洿鎺ユ坊鍔?                    elif isinstance(attr, APIRouter):
                        routers.append((attr_name, attr))
            except Exception as e:
                import_failures.append((module_name, str(e)))
                logger.exception(f'Error importing module {module_name}: {e}')
        return routers, import_failures

    def _sort_routers(self, routers: list[tuple[str, APIRouter]]) -> list[tuple[str, APIRouter]]:
        """
        鎸夎鍒欐帓搴忚矾鐢?
        :param routers: 璺敱瀹炰緥鍒楄〃
        :return: 鎺掑簭鍚庣殑璺敱瀹炰緥鍒楄〃
        """

        def sort_key(item: tuple[str, APIRouter]) -> Union[tuple[Literal[0], int, str], tuple[Literal[1], str]]:
            attr_name, router = item
            # APIRouterPro瀹炰緥鎸塷rder_num鎺掑簭锛屽簭鍙疯秺灏忚秺闈犲墠
            if isinstance(router, APIRouterPro):
                return (0, router.order_num, attr_name)
            return (1, attr_name)

        return sorted(routers, key=sort_key)

    def _register_routers_to_app(self, routers: list[tuple[str, APIRouter]]) -> None:
        """
        灏嗚矾鐢辨敞鍐屽埌FastAPI搴旂敤

        :param routers: 鎺掑簭鍚庣殑璺敱瀹炰緥鍒楄〃
        :return: None
        """
        for _attr_name, router in routers:
            self.app.include_router(router=router)

    def register_routers(self) -> None:
        """
        鑷姩娉ㄥ唽鎵€鏈塩ontroller鐩綍涓嬬殑璺敱

        :return: None
        """
        # 鏌ユ壘鎵€鏈塩ontroller鐩綍涓嬬殑py鏂囦欢
        controller_files = self._find_controller_files()
        logger.info(f'Router auto-register scan completed, controller/api files found: {len(controller_files)}')
        routers, import_failures = self._import_module_and_get_routers(controller_files)
        sorted_routers = self._sort_routers(routers)
        # 娉ㄥ唽璺敱鍒癋astAPI搴旂敤
        self._register_routers_to_app(sorted_routers)
        logger.info(
            'Router auto-register summary: '
            f'scanned={len(controller_files)}, '
            f'registered={len(sorted_routers)}, '
            f'import_failed={len(import_failures)}'
        )
        for module_name, error_msg in import_failures:
            logger.error(f'Router import failure detail: module={module_name}, error={error_msg}')


def auto_register_routers(app: FastAPI) -> None:
    """
    鑷姩娉ㄥ唽鎵€鏈塩ontroller鐩綍涓嬬殑璺敱

    :param app: FastAPI瀵硅薄
    :return: None
    """
    router_register = RouterRegister(app)
    router_register.register_routers()
