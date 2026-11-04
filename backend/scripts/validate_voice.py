"""Explicit, paid voice audition. Never invoked during startup or tests."""
import argparse
import asyncio
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import config
from services.openai_service import synthesize

SAMPLES = [
    "Good morning. Please, take your time. What would you like to discuss today?",
    "The document describes a rotating bucket wheel which excavates material continuously.",
    "I am afraid the indexed papers do not establish that detail. Shall we look at a different question?",
]

async def run(output):
    output.mkdir(parents=True,exist_ok=True)
    for i,text in enumerate(SAMPLES,1):
        (output/f"{config.OPENAI_TTS_VOICE}-{i}.wav").write_bytes(await synthesize(text))
    print("Samples written. Listen for accent, masculine character, pacing and articulation; quality is not automatically validated.")

if __name__=="__main__":
    parser=argparse.ArgumentParser(description="Makes three billable Speech API requests using configured voice.")
    parser.add_argument("--output",type=Path,default=Path("voice-audition"))
    args=parser.parse_args();asyncio.run(run(args.output))
