from io import BytesIO


class VoiceService:
    def __init__(self, client):
        self.client = client

    def transcribe(self, data):
        if not data or len(data) > 20 * 1024 * 1024:
            raise ValueError("음성은 0~20MB 범위의 녹음이어야 합니다.")
        file = BytesIO(data)
        file.name = "recording.wav"
        return self.client.audio.transcriptions.create(
            model="whisper-1", file=file, language="ko",
            prompt="니즈푸드 임진감김치 배합 원료 LOT 검식 출하").text

    def speak(self, text):
        if not text.strip() or len(text) > 3000:
            raise ValueError("음성 재생은 1~3000자 답변에 지원됩니다.")
        response = self.client.audio.speech.create(model="tts-1", voice="alloy", input=text, response_format="mp3")
        return response.read()
