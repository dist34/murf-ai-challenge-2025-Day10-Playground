import json
import logging
import os
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Dict, Optional, Annotated

from dotenv import load_dotenv
from pydantic import Field
from livekit.agents import (
    Agent,
    AgentSession,
    JobContext,
    JobProcess,
    RoomInputOptions,
    WorkerOptions,
    cli,
    function_tool,
    RunContext,
    MetricsCollectedEvent,
    metrics,
    tokenize,
)

from livekit.plugins import murf, silero, google, deepgram, noise_cancellation
from livekit.plugins.turn_detector.multilingual import MultilingualModel

# -------------------------
# Logging
# -------------------------
logger = logging.getLogger("shopping_agent")
logger.setLevel(logging.INFO)
handler = logging.StreamHandler()
handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
logger.addHandler(handler)

load_dotenv(".env.local")


PRODUCTS_FILE = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "products.json")
)
ORDERS_FILE = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "orders.json")
)

if not os.path.exists(ORDERS_FILE):
    with open(ORDERS_FILE, "w") as f:
        json.dump([], f, indent=2)

if not os.path.exists(PRODUCTS_FILE):
    default_data = {
        "products": [
            {
                "id": "hoodie-black-01",
                "name": "Black Warrior Hoodie",
                "price": 1499,
                "currency": "INR",
                "category": "hoodie",
                "color": "black",
                "sizes": ["S", "M", "L", "XL"]
            },
            {
                "id": "hoodie-blue-01",
                "name": "Blue Mystic Hoodie",
                "price": 1299,
                "currency": "INR",
                "category": "hoodie",
                "color": "blue",
                "sizes": ["M", "L"]
            },
            {
                "id": "mug-white-01",
                "name": "Stoneware Coffee Mug",
                "price": 800,
                "currency": "INR",
                "category": "mug",
                "color": "white"
            },
            {
                "id": "mug-blue-01",
                "name": "Midnight Blue Mug",
                "price": 650,
                "currency": "INR",
                "category": "mug",
                "color": "blue"
            }
        ]
    }
    with open(PRODUCTS_FILE, "w") as f:
        json.dump(default_data, f, indent=2)



@dataclass
class Userdata:
    customer_name: Optional[str] = None
    session_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    started_at: str = field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")
    cart: List[Dict] = field(default_factory=list)
    orders: List[Dict] = field(default_factory=list)
    history: List[Dict] = field(default_factory=list)

#
def _load_data() -> Dict:
    """Load products and orders from JSON file"""
    try:
        with open(PRODUCTS_FILE, 'r') as f:
            data = json.load(f)
            logger.info(f"Loaded {len(data.get('products', []))} products and {len(data.get('orders', []))} orders")
            return data
    except Exception as e:
        logger.error(f"Error loading data: {e}")
        return {"products": [], "orders": []}

def _save_order(order: Dict):
    """Save order to a separate orders.json file"""
    try:
        # Load existing orders
        if os.path.exists(ORDERS_FILE):
            with open(ORDERS_FILE, "r") as f:
                orders = json.load(f)
        else:
            orders = []

        # Append new order
        orders.append(order)

        # Save into orders.json (NOT products.json)
        with open(ORDERS_FILE, "w") as f:
            json.dump(orders, f, indent=2)

        logger.info(f"Saved order {order['id']} to orders.json")
    except Exception as e:
        logger.error(f"Error saving order: {e}")



def list_products(filters: Optional[Dict] = None) -> List[Dict]:
    """List products with optional filters"""
    data = _load_data()
    products = data.get("products", [])
    
    if not filters:
        return products
    
    results = products
    category = filters.get("category")
    max_price = filters.get("max_price")
    min_price = filters.get("min_price")
    color = filters.get("color")
    query = filters.get("q")
    
    # Category filter
    if category:
        cat = category.lower()
        results = [p for p in results if p.get("category", "").lower() == cat]
    
    # Price filters
    if max_price:
        try:
            results = [p for p in results if p.get("price", 0) <= int(max_price)]
        except:
            pass
    
    if min_price:
        try:
            results = [p for p in results if p.get("price", 0) >= int(min_price)]
        except:
            pass
    
    # Color filter
    if color:
        results = [p for p in results if p.get("color", "").lower() == color.lower()]
    
    # Query filter
    if query:
        q = query.lower()
        results = [p for p in results if q in p.get("name", "").lower() or q in p.get("category", "").lower()]
    
    logger.info(f"Filtered products: {len(results)} results")
    return results

def find_product_by_ref(ref_text: str, candidates: Optional[List[Dict]] = None) -> Optional[Dict]:
    """Resolve product references like 'second hoodie' or 'black hoodie' or product ID"""
    ref = (ref_text or "").lower().strip()
    cand = candidates if candidates is not None else _load_data().get("products", [])
    
    # Ordinal handling
    ordinals = {"first": 0, "second": 1, "third": 2, "fourth": 3}
    for word, idx in ordinals.items():
        if word in ref:
            if idx < len(cand):
                return cand[idx]
    
    # Direct ID match
    for p in cand:
        if p["id"].lower() == ref:
            return p
    
    # Color + category matching
    for p in cand:
        if p.get("color") and p["color"].lower() in ref and p.get("category") and p["category"].lower() in ref:
            return p
    
    # Name substring matching
    for p in cand:
        name = p["name"].lower()
        if all(tok in name for tok in ref.split() if len(tok) > 2):
            return p
    
    # Numeric index
    for token in ref.split():
        if token.isdigit():
            idx = int(token) - 1
            if 0 <= idx < len(cand):
                return cand[idx]
    
    return None

def create_order_object(line_items: List[Dict], currency: str = "INR") -> Dict:
    """Create order from line items and persist"""
    data = _load_data()
    products = data.get("products", [])
    
    items = []
    total = 0
    
    for li in line_items:
        pid = li.get("product_id")
        qty = int(li.get("quantity", 1))
        prod = next((p for p in products if p["id"] == pid), None)
        
        if not prod:
            raise ValueError(f"Product {pid} not found")
        
        line_total = prod["price"] * qty
        total += line_total
        
        item = {
            "product_id": pid,
            "name": prod["name"],
            "unit_price": prod["price"],
            "quantity": qty,
            "line_total": line_total,
            "attrs": li.get("attrs", {}),
        }
        items.append(item)
    
    order = {
        "id": f"order-{str(uuid.uuid4())[:8]}",
        "items": items,
        "total": total,
        "currency": currency,
        "status": "CONFIRMED",
        "created_at": datetime.utcnow().isoformat() + "Z",
    }
    
    # Save order to products.json
    _save_order(order)
    
    return order

def get_most_recent_order() -> Optional[Dict]:
    """Get the most recent order"""
    data = _load_data()
    orders = data.get("orders", [])
    if not orders:
        return None
    return orders[-1]

# -------------------------
# Agent Tools
# -------------------------
@function_tool
async def show_catalog(
    ctx: RunContext[Userdata],
    q: Annotated[Optional[str], Field(description="Search query (optional)", default=None)] = None,
    category: Annotated[Optional[str], Field(description="Category like 'mug' or 'hoodie' (optional)", default=None)] = None,
    max_price: Annotated[Optional[int], Field(description="Maximum price in INR (optional)", default=None)] = None,
    color: Annotated[Optional[str], Field(description="Color like 'black', 'blue', 'white' (optional)", default=None)] = None,
) -> str:
    """Show products matching the filters. Returns spoken summary with product names, prices, and IDs."""
    logger.info(f"show_catalog called - q: {q}, category: {category}, max_price: {max_price}, color: {color}")
    
    filters = {"q": q, "category": category, "max_price": max_price, "color": color}
    prods = list_products({k: v for k, v in filters.items() if v is not None})
    
    if not prods:
        return "Sorry, I couldn't find any products matching your criteria. Try browsing all hoodies or mugs?"
    
    # Show top 6 products
    lines = [f"I found {len(prods)} product(s). Here are the top {min(6, len(prods))}:"]
    for idx, p in enumerate(prods[:6], start=1):
        size_info = f" (sizes: {', '.join(p['sizes'])})" if p.get('sizes') else ""
        lines.append(f"{idx}. {p['name']} — ₹{p['price']} (ID: {p['id']}){size_info}")
    
    lines.append("Say 'add the second item to my cart in size M' or 'add hoodie-black-01 to cart'.")
    return "\n".join(lines)

@function_tool
async def add_to_cart(
    ctx: RunContext[Userdata],
    product_ref: Annotated[str, Field(description="Product reference: ID, name, or 'first/second/third item'")] ,
    quantity: Annotated[int, Field(description="Quantity", default=1)] = 1,
    size: Annotated[Optional[str], Field(description="Size for clothing items (S, M, L, XL)", default=None)] = None,
) -> str:
    """Add a product to the shopping cart."""
    logger.info(f"add_to_cart called - product_ref: {product_ref}, quantity: {quantity}, size: {size}")
    
    userdata = ctx.userdata
    
    # Resolve product
    prod = find_product_by_ref(product_ref)
    if not prod:
        return f"I couldn't find the product '{product_ref}'. Try saying 'show catalog' to see available items."
    
    # Check if size is required for clothing
    if prod.get("sizes") and not size:
        return f"Please specify a size for {prod['name']}. Available sizes: {', '.join(prod['sizes'])}"
    
    # Add to cart
    userdata.cart.append({
        "product_id": prod["id"],
        "quantity": int(quantity),
        "attrs": {"size": size} if size else {},
    })
    
    userdata.history.append({
        "time": datetime.utcnow().isoformat() + "Z",
        "action": "add_to_cart",
        "product_id": prod["id"],
        "quantity": int(quantity),
    })
    
    size_text = f" in size {size}" if size else ""
    return f"Added {quantity} x {prod['name']}{size_text} to your cart. Say 'show cart' to review or 'place order' to checkout."

@function_tool
async def show_cart(ctx: RunContext[Userdata]) -> str:
    """Show all items currently in the shopping cart."""
    logger.info("show_cart called")
    
    userdata = ctx.userdata
    
    if not userdata.cart:
        return "Your cart is empty. Say 'show catalog' to browse products."
    
    data = _load_data()
    products = data.get("products", [])
    
    lines = ["Items in your cart:"]
    total = 0
    
    for li in userdata.cart:
        p = next((x for x in products if x["id"] == li["product_id"]), None)
        if not p:
            continue
        
        line_total = p["price"] * li.get("quantity", 1)
        total += line_total
        
        sz = li.get("attrs", {}).get("size")
        sz_text = f", size {sz}" if sz else ""
        lines.append(f"- {p['name']} x {li['quantity']}{sz_text}: ₹{line_total}")
    
    lines.append(f"\nCart total: ₹{total}")
    lines.append("Say 'place my order' to checkout or 'clear cart' to empty the cart.")
    
    return "\n".join(lines)

@function_tool
async def clear_cart(ctx: RunContext[Userdata]) -> str:
    """Empty the shopping cart."""
    logger.info("clear_cart called")
    
    userdata = ctx.userdata
    userdata.cart = []
    userdata.history.append({
        "time": datetime.utcnow().isoformat() + "Z",
        "action": "clear_cart"
    })
    
    return "Your cart has been cleared. Would you like to browse the catalog?"

@function_tool
async def place_order(
    ctx: RunContext[Userdata],
    confirm: Annotated[bool, Field(description="Confirm order placement", default=True)] = True,
) -> str:
    """Place an order with items from the cart. Saves order to products.json."""
    logger.info("place_order called")
    
    userdata = ctx.userdata
    
    if not userdata.cart:
        return "Your cart is empty. Add some items first by saying 'show catalog'."
    
    # Create line items
    line_items = []
    for li in userdata.cart:
        line_items.append({
            "product_id": li["product_id"],
            "quantity": li.get("quantity", 1),
            "attrs": li.get("attrs", {}),
        })
    
    # Create and save order
    order = create_order_object(line_items)
    userdata.orders.append(order)
    userdata.history.append({
        "time": datetime.utcnow().isoformat() + "Z",
        "action": "place_order",
        "order_id": order["id"]
    })
    
    # Clear cart
    userdata.cart = []
    
    lines = [f"Order confirmed! Order ID: {order['id']}"]
    lines.append("\nItems ordered:")
    for it in order['items']:
        sz = it['attrs'].get('size')
        sz_text = f" (size {sz})" if sz else ""
        lines.append(f"- {it['name']} x {it['quantity']}{sz_text}: ₹{it['line_total']}")
    lines.append(f"\nTotal: ₹{order['total']} {order['currency']}")
    lines.append("\nYour order has been saved. Say 'last order' to review it anytime.")
    
    return "\n".join(lines)

@function_tool
async def last_order(ctx: RunContext[Userdata]) -> str:
    """Show the most recent order details."""
    logger.info("last_order called")
    
    ord = get_most_recent_order()
    
    if not ord:
        return "You haven't placed any orders yet. Say 'show catalog' to start shopping."
    
    lines = [f"Your last order: {ord['id']}"]
    lines.append(f"Placed on: {ord['created_at']}")
    lines.append("\nItems:")
    
    for it in ord['items']:
        sz = it.get('attrs', {}).get('size')
        sz_text = f" (size {sz})" if sz else ""
        lines.append(f"- {it['name']} x {it['quantity']}{sz_text}: ₹{it['line_total']}")
    
    lines.append(f"\nTotal: ₹{ord['total']} {ord['currency']}")
    lines.append(f"Status: {ord.get('status', 'CONFIRMED')}")
    
    return "\n".join(lines)

# -------------------------
# Shopping Assistant Agent
# -------------------------
class ShoppingAssistant(Agent):
    def __init__(self):
        instructions = """
        You are a friendly voice shopping assistant for an online store.
        
        Store: We sell hoodies and coffee mugs in various colors and sizes.
        Tone: Warm, helpful, conversational. Keep responses concise for voice delivery.
        
        Your job:
        - Help customers browse the catalog using show_catalog
        - Add items to their cart using add_to_cart
        - Show cart contents using show_cart
        - Place orders using place_order
        - Show last order using last_order
        - Clear cart using clear_cart
        
        Guidelines:
        - Always mention product IDs when listing products
        - For clothing items, ask for size if not provided
        - Confirm additions to cart clearly
        - Keep responses short and natural for voice
        - Guide customers through the shopping flow
        
        Example flow:
        Customer: "Show me hoodies"
        You: Use show_catalog with category="hoodie"
        
        Customer: "Add the first one in size M"
        You: Use add_to_cart with the product reference and size
        
        Customer: "Place my order"
        You: Use place_order to complete the purchase
        """
        
        super().__init__(
            instructions=instructions,
            tools=[show_catalog, add_to_cart, show_cart, clear_cart, place_order, last_order],
        )

# -------------------------
# Entrypoint
# -------------------------
def prewarm(proc: JobProcess):
    try:
        proc.userdata["vad"] = silero.VAD.load()
        logger.info("VAD model prewarmed successfully")
    except Exception as e:
        logger.warning(f"VAD prewarm failed: {e}")

async def entrypoint(ctx: JobContext):
    ctx.log_context_fields = {"room": ctx.room.name}
    logger.info("🛍️ Starting Voice Shopping Assistant")
    
    userdata = Userdata()
    
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
        vad=ctx.proc.userdata.get("vad"),
        userdata=userdata,
    )
    
    # Metrics
    usage_collector = metrics.UsageCollector()
    
    @session.on("metrics_collected")
    def _on_metrics_collected(ev: MetricsCollectedEvent):
        metrics.log_metrics(ev.metrics)
        usage_collector.collect(ev.metrics)
    
    async def log_usage():
        summary = usage_collector.get_summary()
        logger.info(f"Usage: {summary}")
    
    ctx.add_shutdown_callback(log_usage)
    
    await session.start(
        agent=ShoppingAssistant(),
        room=ctx.room,
        room_input_options=RoomInputOptions(
            noise_cancellation=noise_cancellation.BVC(),
        ),
    )
    
    await ctx.connect()

if __name__ == "__main__":
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint, prewarm_fnc=prewarm))