# server.py
import asyncio, json, base64, os, time
from websockets import serve
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

import websockets
print("WEBSOCKETS VERSION:", websockets.__version__)

# ======================================================
#   CONFIG: MASTER KEY
# ======================================================
K_MASTER = os.environ.get("K_MASTER")  # base64

if K_MASTER is None:
    print("⚠️  WARNING: Generando K_MASTER temporal (solo dev)")
    K_MASTER = AESGCM.generate_key(bit_length=256)
else:
    print("Usando K_MASTER desde variable de entorno")
    K_MASTER = base64.b64decode(K_MASTER)

aes = AESGCM(K_MASTER)

# sesiones activas
SESSIONS = {}

# ======================================================
#   TOKEN CREATION
# ======================================================
def make_token(read_only=True, ttl_seconds=3600):
    k_session = os.urandom(32)
    expires = int(time.time()) + ttl_seconds

    meta = json.dumps({
        "k": base64.b64encode(k_session).decode(),
        "ro": read_only,
        "exp": expires
    }).encode()

    nonce = os.urandom(12)
    ciphertext = aes.encrypt(nonce, meta, None)
    token = base64.b64encode(nonce + ciphertext).decode()

    SESSIONS[token] = {
        "k_session": k_session,
        "read_only": read_only,
        "expires": expires,
        "host_ws": None,
        "viewer_ws": None,
        "control_granted": False
    }
    return token

def validate_and_get_session(token):
    entry = SESSIONS.get(token)
    if not entry:
        return None
    if entry["expires"] < time.time():
        del SESSIONS[token]
        return None
    return entry

# ======================================================
#   HANDLER
# ======================================================
async def handler(ws):
    try:
        msg = await ws.recv()
    except Exception as e:
        print("Error recibiendo primer mensaje:", e)
        await ws.close()
        return

    try:
        obj = json.loads(msg)
    except:
        await ws.send(json.dumps({"type": "error", "msg": "invalid json"}))
        await ws.close()
        return

    role = obj.get("role")
    token = obj.get("token")
    session = validate_and_get_session(token)

    if session is None:
        await ws.send(json.dumps({"type": "error", "msg": "invalid token"}))
        await ws.close()
        return

    print(f"[+] Nueva conexión {role} (read_only={session['read_only']})")

    # ======================================================
    #   HOST
    # ======================================================
    if role == "host":
        session["host_ws"] = ws
        await ws.send(json.dumps({"type": "ok", "role": "host", "read_only": session["read_only"]}))

        try:
            async for m in ws:
                if isinstance(m, bytes):
                    v = session.get("viewer_ws")
                    if v:
                        await v.send(m)
                else:
                    pass

        finally:
            print("[!] Host desconectado")
            session["host_ws"] = None

    # ======================================================
    #   VIEWER
    # ======================================================
    elif role == "viewer":
        session["viewer_ws"] = ws
        await ws.send(json.dumps({"type": "ok", "role": "viewer", "read_only": session["read_only"]}))

        try:
            async for m in ws:
                if not isinstance(m, str):
                    continue

                data = json.loads(m)
                t = data.get("type")

                if t == "req_control":
                    host = session.get("host_ws")
                    if host:
                        await host.send(json.dumps({"type": "control_request"}))

                elif t == "input_event":
                    if not session["control_granted"]:
                        await ws.send(json.dumps({"type": "error", "msg": "control not granted"}))
                    else:
                        host = session["host_ws"]
                        if host:
                            await host.send(json.dumps({
                                "type": "input_event",
                                "event": data.get("event")
                            }))
        finally:
            print("[!] Viewer desconectado")
            session["viewer_ws"] = None

# ======================================================
#   MAIN
# ======================================================
async def main():
    token = make_token(read_only=True, ttl_seconds=3600)
    print("Token ejemplo (read-only):", token)

    async with serve(handler, "0.0.0.0", 8765):
        print("Server listening 0.0.0.0:8765")
        await asyncio.Future()

if __name__ == "__main__":
    asyncio.run(main())
