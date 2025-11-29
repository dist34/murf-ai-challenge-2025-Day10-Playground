import logging

from dotenv import load_dotenv
from livekit.agents import (
    Agent,
    AgentSession,
    JobContext,
    JobProcess,
    MetricsCollectedEvent,
    RoomInputOptions,
    WorkerOptions,
    cli,
    metrics,
    tokenize,
)
from livekit.plugins import murf, silero, google, deepgram, noise_cancellation
from livekit.plugins.turn_detector.multilingual import MultilingualModel

logger = logging.getLogger("agent")

load_dotenv(".env.local")

# ------------------------------
# Game Master Agent Definition
# ------------------------------

class GameMaster(Agent):
    def __init__(self) -> None:
        super().__init__(
            instructions="""
You are a Game Master (GM) running a voice-only D&D-style adventure.

BEFORE THE STORY:
Always begin by asking:
"Greetings, adventurer. What is your name?"
Wait for the player to answer. Do NOT start the story until the player gives their name.
Once a name is given, remember it and use it throughout the adventure.

UNIVERSE:
A fantasy land of magic, ruins, creatures, and ancient mysteries.

TONE:
Cinematic, adventurous, immersive — with gradual tension.

PACING:
- Do NOT start combat immediately.
- Allow 1–2 turns of exploration after the player gives their name.
- Introduce danger around turn 3.
- Move toward combat naturally around turn 4–5.

CHOICE SYSTEM:
After every GM message, ALWAYS give exactly three numbered choices:
1. A bold or direct action
2. A cautious or defensive action
3. A creative or alternative action

RESTART RULE:
• You must NOT offer a restart option before turn 4.
• AFTER turn 4, you MAY replace choice #3 with:
  "Restart the story."

If the player chooses to restart, you MUST reset fully and say:
"Your journey begins anew. Greetings, adventurer. What is your name?"

RULES:
- Maintain continuity using ONLY chat history.
- Always remember the player's name.
- Choices must be relevant to the current scene.
- Keep responses 4–7 sentences.
- Never decide the player's actions.
- ALWAYS end with: "What do you do?"
"""

        )

    async def on_start(self, session: AgentSession):
        """Ask for name BEFORE starting the story."""

        await session.llm.set_system_message(self.instructions)

        await session.say(
            "Greetings, adventurer. I cannot guide you without knowing who you are. "
            "Tell me—what is your name?"
        )


# ------------------------------
# Prewarm
# ------------------------------

def prewarm(proc: JobProcess):
    proc.userdata["vad"] = silero.VAD.load()


# ------------------------------
# Entrypoint
# ------------------------------

async def entrypoint(ctx: JobContext):
    ctx.log_context_fields = {
        "room": ctx.room.name,
    }

    session = AgentSession(
        stt=deepgram.STT(model="nova-3"),
        llm=google.LLM(model="gemini-2.5-flash"),
        tts=murf.TTS(
            voice="en-US-matthew",
            style="Conversation",
            tokenizer=tokenize.basic.SentenceTokenizer(min_sentence_len=2),
            text_pacing=True
        ),
        turn_detection=MultilingualModel(),
        vad=ctx.proc.userdata["vad"],
        preemptive_generation=False,  # prevents random intro
    )

    usage_collector = metrics.UsageCollector()

    @session.on("metrics_collected")
    def _on_metrics(ev: MetricsCollectedEvent):
        metrics.log_metrics(ev.metrics)
        usage_collector.collect(ev.metrics)

    async def log_usage():
        logger.info(f"Usage Summary: {usage_collector.get_summary()}")

    ctx.add_shutdown_callback(log_usage)

    # Start session / voice pipeline
    await session.start(
        agent=GameMaster(),
        room=ctx.room,
        room_input_options=RoomInputOptions(
            noise_cancellation=noise_cancellation.BVC(),
        ),
    )

    await ctx.connect()


# ------------------------------
# Worker Start
# ------------------------------

if __name__ == "__main__":
    cli.run_app(
        WorkerOptions(
            entrypoint_fnc=entrypoint,
            prewarm_fnc=prewarm
        )
    )
