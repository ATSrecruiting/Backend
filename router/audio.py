from fastapi import UploadFile, HTTPException, APIRouter
import whisper
import tempfile
import os
from schema.audio import TranscribeAudioResponse

router = APIRouter()


model = whisper.load_model("base")


@router.post("/transcribe/")
async def transcribe_audio(audio: UploadFile):
    if not audio.filename.endswith((".wav", ".mp3", ".m4a", ".webm")):
        raise HTTPException(status_code=400, detail="Unsupported file format")

    try:

        with tempfile.NamedTemporaryFile(
            delete=False, suffix=os.path.splitext(audio.filename)[1]
        ) as temp_file:

            content = await audio.read()
            temp_file.write(content)
            temp_file.flush()


            result = model.transcribe(temp_file.name)


            os.unlink(temp_file.name)

            res = TranscribeAudioResponse(
                text=result["text"], segments=result["segments"]
            )

            return res

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
