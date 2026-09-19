# CMFit OpenAI Chat Update

## Files
Copy these paths into the matching locations in `~/cmfit`:
- `app.py`
- `templates/base.html`
- `templates/log_workout.html`
- `static/css/style.css`
- `services/llm_provider.py`
- `services/openai_provider.py`
- `services/mcp_chat_client.py`
- `services/chat_service.py`

This update assumes your existing `mcp_server.py` with the 21 tested CMFit tools remains in the project root.

## Dependency
From the CMFit virtual environment:

    pip install -U openai

Keep your existing MCP dependency (`mcp>=2,<3`).

## Environment
Add to `.env` (do not put the key in HTML or JavaScript):

    OPENAI_API_KEY=your_key_here
    CMFIT_LLM_PROVIDER=openai
    CMFIT_OPENAI_MODEL=gpt-5.6-luna

Optional if the Flask process cannot find the same Python used by CMFit/MCP:

    CMFIT_PYTHON=/home/mfsli1/cmfit/venv/bin/python

## Architecture
Browser -> POST /chat -> chat_service -> LLMProvider -> OpenAIProvider -> MCP client -> mcp_server.py -> service layer -> cmfit.db

To add another LLM later, subclass `LLMProvider`, implement `chat()`, and add it to `_provider()` in `services/chat_service.py`. UI and MCP code do not need to change.

## Voice
The browser uses `SpeechRecognition` / `webkitSpeechRecognition` when Safari exposes it. If unavailable, the drawer remains usable with text.

## Test
1. Restart CMFit.
2. Open any page and tap the chat icon in the header.
3. Ask: `What were my last 3 workouts?`
4. On an active workout, tap the microphone beside Save.
5. Say: `10 reps 95 pounds starting heart rate 140 ending heart rate 100 with 60 seconds rest`.
6. The agent should call `log_set`, then `save_rest`, and the workout page reloads to show the logged row.
