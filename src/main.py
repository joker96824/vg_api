from fastapi import FastAPI, HTTPException
from fastapi.responses import RedirectResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware
from config.settings import settings
from .api.v1.api import api_router
from .core.logging import root_logger  # 导入日志配置

logger = root_logger.getChild(__name__)

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    openapi_url=f"/api/v1/openapi.json",
    docs_url=None,  # 禁用默认的 docs
    redoc_url=None  # 禁用默认的 redoc
)

# 配置CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  # 明确指定允许的源
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],  # 明确指定允许的方法
    allow_headers=["Content-Type", "Authorization", "Accept"],  # 明确指定允许的头部
    expose_headers=["*"],  # 允许暴露所有头部
)

# 添加会话中间件
app.add_middleware(
    SessionMiddleware,
    secret_key=settings.SESSION_SECRET_KEY,  # 使用环境变量中的密钥
    session_cookie="session",
    max_age=1800,  # 30分钟过期
    same_site="lax",
    https_only=False  # 开发环境可以设置为False
)

# 添加重定向路由
@app.get("/cards")
async def redirect_cards():
    return RedirectResponse(url="/api/v1/cards")

@app.get("/cards/{path:path}")
async def redirect_cards_path(path: str):
    return RedirectResponse(url=f"/api/v1/cards/{path}")

# 注册路由
app.include_router(api_router, prefix="/api/v1")

# 挂载静态文件服务
app.mount("/image", StaticFiles(directory="../image"), name="image")

@app.get("/")
async def root():
    return {"message": "Welcome to Vanguard API"}

# 自定义 Swagger UI 路由
@app.get("/docs", include_in_schema=False)
async def custom_swagger_ui_html():
    return get_swagger_ui_html(
        openapi_url="/api/v1/openapi.json",
        title=f"{settings.APP_NAME} - Swagger UI",
        swagger_js_url="https://unpkg.com/swagger-ui-dist@5.9.0/swagger-ui-bundle.js",
        swagger_css_url="https://unpkg.com/swagger-ui-dist@5.9.0/swagger-ui.css",
    )

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "src.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,  # 启用热重载
        log_level="debug",  # 设置日志级别为 debug
        workers=settings.WORKERS,
    ) 