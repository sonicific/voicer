import asyncio
import edge_tts

async def main():
    communicate = edge_tts.Communicate(
        text="Xin chào, đây là giọng Microsoft Edge rất tự nhiên",
        voice="vi-VN-HoaiMyNeural"
    )
    await communicate.save("edge.mp3")

asyncio.run(main())
