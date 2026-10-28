import logging
import re
import time
from contextlib import asynccontextmanager
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from redis.asyncio import Redis
from sqlalchemy import text
from starlette.exceptions import HTTPException

from app.core.config import get_settings
from app.core.database import create_engines
from app.modules.auth.router import router as auth_router
from app.modules.meta.router import router as meta_router
from app.modules.perdas.router import router as perdas_router

logger = logging.getLogger('venergy.requests')


def create_app(settings=None):
    settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app):
        logging.basicConfig(
            level=logging.INFO, format='%(asctime)s %(levelname)s %(name)s %(message)s'
        )
        app.state.settings = settings
        app.state.portal_engine, app.state.ai_engine = create_engines(settings)
        app.state.redis = Redis.from_url(
            settings.redis_url, socket_connect_timeout=2, socket_timeout=2
        )
        try:
            yield
        finally:
            await app.state.redis.aclose()
            await app.state.portal_engine.dispose()
            await app.state.ai_engine.dispose()

    app = FastAPI(title='V-Energy Grid 360', version='0.1.0', lifespan=lifespan)

    @app.middleware('http')
    async def request_log(request: Request, call_next):
        supplied = request.headers.get('X-Request-ID', '')
        request_id = supplied if re.fullmatch(r'[A-Za-z0-9_-]{1,64}', supplied) else str(uuid4())
        request.state.request_id = request_id
        start = time.monotonic()
        try:
            response = await call_next(request)
        except Exception:
            # Sem corpo, SQL, credenciais ou parâmetros nos logs.
            logger.error('request_id=%s method=%s status=500', request_id, request.method)
            response = JSONResponse(
                status_code=500, content={'detail': 'Erro interno', 'code': 'ERRO_INTERNO'}
            )
        response.headers['X-Request-ID'] = request_id
        logger.info(
            'request_id=%s method=%s status=%s duration_ms=%.1f',
            request_id,
            request.method,
            response.status_code,
            (time.monotonic() - start) * 1000,
        )
        return response

    @app.exception_handler(HTTPException)
    async def http_error(request, exc):
        codes = {401: 'NAO_AUTENTICADO', 403: 'SEM_PERMISSAO', 404: 'NAO_ENCONTRADO'}
        headers = dict(exc.headers or {})
        if exc.status_code == 401:
            headers['WWW-Authenticate'] = 'Bearer'
        return JSONResponse(
            status_code=exc.status_code,
            headers=headers,
            content={
                'detail': exc.detail,
                'code': getattr(exc, 'code', codes.get(exc.status_code, 'ERRO')),
            },
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error(request, exc):
        # Não devolve input/context, que podem incluir senhas do login.
        errors = [
            {'campo': '.'.join(map(str, e['loc'])), 'mensagem': e['msg']} for e in exc.errors()
        ]
        return JSONResponse(
            status_code=422, content={'detail': errors, 'code': 'VALIDACAO_INVALIDA'}
        )

    @app.get('/api/v1/health', tags=['health'])
    async def health():
        checks = {}
        try:
            async with app.state.portal_engine.connect() as connection:
                await connection.execute(text('SELECT 1'))
            checks['postgres'] = 'ok'
        except Exception:
            checks['postgres'] = 'indisponivel'
        try:
            await app.state.redis.ping()
            checks['redis'] = 'ok'
        except Exception:
            checks['redis'] = 'indisponivel'
        if any(v != 'ok' for v in checks.values()):
            return JSONResponse(
                status_code=503, content={'detail': checks, 'code': 'SERVICO_INDISPONIVEL'}
            )
        return {'status': 'ok', **checks}

    for router in (auth_router, meta_router, perdas_router):
        app.include_router(router, prefix='/api/v1')
    return app


app = create_app()
