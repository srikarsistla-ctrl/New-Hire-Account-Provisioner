"""Isolated UI QA server. Never reads or changes the user's database or AI keys."""
import os
from pathlib import Path
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
with tempfile.TemporaryDirectory(prefix='provision-ui-') as folder:
    os.environ['DATABASE_URL'] = 'sqlite:///' + (Path(folder) / 'preview.db').as_posix()
    os.environ['GROQ_API_KEY'] = ''
    os.environ['OPENAI_API_KEY'] = ''
    import uvicorn
    uvicorn.run('app.main:app', host='127.0.0.1', port=8015)
