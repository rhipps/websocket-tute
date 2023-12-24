#!/usr/bin/env py

import asyncio
import json
import secrets

import websockets
from connect4 import PLAYER1, PLAYER2, Connect4


async def play(websocket, game, player, connected):
    async for message in websocket:
        try:
            event = json.loads(message)
            current_player = player
            row = game.play(current_player, event['column'])
            event = {
                "type": "play",
                "player": current_player,
                "column": event['column'],
                "row": row,
            }
        except RuntimeError as error:
            event = {
                "type": "error",
                "message": str(error)
            }
        websockets.broadcast(connected, json.dumps(event))
        await asyncio.sleep(0.5)
        await check_if_player_won(game, connected)

JOIN = {}

async def start(websocket):
    # Initialize a Connect Four game, the set of WebSocket connections
    # receiving moves from this game, and secret access token.
    game = Connect4()
    connected = {websocket}

    join_key = secrets.token_urlsafe(12)
    JOIN[join_key] = game, connected

    try:
        # Send the secret access token to the browser of the first player,
        # where it'll be used for building a "join" link.
        event = {
            "type": "init",
            "join": join_key,
        }
        await websocket.send(json.dumps(event))

        # Temporary - for testing.
        await play(websocket, game, PLAYER1, connected)

    finally:
        del JOIN[join_key]


async def handler(websocket):
    # Receive and parse the "init" event from the UI.
    message = await websocket.recv()
    event = json.loads(message)
    assert event["type"] == "init"

    if "join" in event:
        # Second player joins an existing game.
        await join(websocket, event["join"])
    else:
        # First player starts a new game.
        await start(websocket)

async def error(websocket, message):
    event = {
        "type": "error",
        "message": message,
    }
    await websocket.send(json.dumps(event))

async def join(websocket, join_key):
    # Find the Connect Four game.
    try:
        game, connected = JOIN[join_key]
    except KeyError:
        await error(websocket, "Game not found.")
        return

    # Register to receive moves from this game.
    connected.add(websocket)
    try:

        await play(websocket, game, PLAYER2, connected)

    finally:
        connected.remove(websocket)


async def check_if_player_won(game, connected):
    if game.last_player_won:
        event = {
            "type": "win",
            "player": game.winner,
        }
        websockets.broadcast(connected, json.dumps(event))

async def main():
    async with websockets.serve(handler, "", 8010):
        await asyncio.Future()  # run forever

if __name__ == "__main__":
    asyncio.run(main())