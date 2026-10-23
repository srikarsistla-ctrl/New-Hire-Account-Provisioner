from fastapi import Request, HTTPException
from fastapi.responses import Response
from workers import asgi
from cloudflare.api import create_app

app = create_app()
Default = asgi.entrypoint(app)


@app.get('/{path:path}')
async def assets(request: Request, path: str):
    if path.startswith('api/'):
        raise HTTPException(404, 'Unknown API endpoint')
    response = await request.scope['env'].ASSETS.fetch(str(request.url))
    return Response(content=await response.bytes(), status_code=response.status,
                    headers=dict(response.headers))
