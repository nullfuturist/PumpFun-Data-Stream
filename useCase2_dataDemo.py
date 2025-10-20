import asyncio
import json
import websockets
import base64
import base58
import struct
import sys

swap_received = False
creation_received = False

async def logsSubscribe(ws, address):
    await ws.send(json.dumps({
        "jsonrpc": "2.0",
        "id": 1,
        "method": "logsSubscribe",
        "params": [
            {"mentions": [address]},
            {"commitment": "confirmed"}
        ]
    }))    
    response = json.loads(await ws.recv())
    if not "result" in response:
        print(response)
        sys.exit(1)
    return response["result"]

def on_token_creation(sig, slot, name, symbol, uri, mint, curve, user, creator):
    global creation_received
    if creation_received:
        return
    creation_received = True
    print("=== TOKEN CREATION ===")
    print(f"Signature: {sig}")
    print(f"Slot: {slot}")
    print(f"Name: {name}")
    print(f"Symbol: {symbol}")
    print(f"URI: {uri}")
    print(f"Mint: {mint}")
    print(f"Curve: {curve}")
    print(f"User: {user}")
    print(f"Creator: {creator}")
    print()

def on_swap(sig, slot, timestamp, mint, user, is_buy, sol_amount, token_amount, v_sol_reserves, v_token_reserves, r_sol_reserves, r_token_reserves):
    global swap_received
    if swap_received:
        return
    swap_received = True
    
    sol_val = sol_amount / 1e9
    token_val = token_amount / 1e6
    v_sol = v_sol_reserves / 1e9
    v_token = v_token_reserves / 1e6
    r_sol = r_sol_reserves / 1e9
    r_token = r_token_reserves / 1e6
    
    price_after_swap = v_sol / v_token if v_token > 0 else 0
    swap_price = sol_val / token_val if token_val > 0 else 0
    
    print("=== SWAP ===")
    print(f"Signature: {sig}")
    print(f"Slot: {slot}")
    print(f"Timestamp: {timestamp}")
    print(f"Mint: {mint}")
    print(f"User: {user}")
    print(f"Is Buy: {is_buy}")
    print(f"SOL Amount: {sol_val:.6f} SOL")
    print(f"Token Amount: {token_val:.6f}")
    print(f"Virtual SOL Reserves: {v_sol:.6f} SOL [reserve state after swap]")
    print(f"Virtual Token Reserves: {v_token:.6f}")
    print(f"Real SOL Reserves: {r_sol:.6f} SOL")
    print(f"Real Token Reserves: {r_token:.6f}")
    print(f"Swap Price:       {swap_price:.12f} SOL/token")
    print(f"Price After Swap: {price_after_swap:.12f} virt. res. SOL/token")
    print()

async def runAsync():
    ws = await websockets.connect("wss://mainnet.helius-rpc.com/?api-key=9e7ab923-d89b-4506-9b9e-618f58b12ca2")
    sub_id_token_creation = await logsSubscribe(ws, "TSLvdd1pWpHVjahSpsvCXUbgwsL3JAcvokwaKt1eokM")
    sub_id_swap = await logsSubscribe(ws, "6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P")
    
    while not (swap_received and creation_received):
        try:
            data = json.loads(await ws.recv())
        except Exception as e:
            print(f"Error: {e}")
            continue
            
        result = data["params"]["result"]
        err = result["value"]["err"]
        if err != None:
            continue
        slot = result["context"]["slot"]
        signature = result["value"]["signature"]
        logs = result["value"]["logs"]
        
        program_data_logs = map(
            lambda x: base64.b64decode(x[14:]), 
            filter(lambda x: x[:14]=="Program data: ", logs)
        )
        
        sub_id = data["params"]["subscription"]
        if sub_id == sub_id_token_creation and not creation_received:
            token_creations = filter(
                lambda x: x[0:8].hex() == "1b72a94ddeeb6376",
                program_data_logs
            )
            for data in token_creations:
                len_name, = struct.unpack("<I", data[8:12])
                offset = 12 + len_name
                len_symbol, = struct.unpack("<I", data[offset:offset+4])
                offset += 4 + len_symbol
                len_uri, = struct.unpack("<I", data[offset:offset+4])
                _,name,_,symbol,_,uri,mint,curve,user,creator,timestamp = struct.unpack(
                    f"<I{len_name}sI{len_symbol}sI{len_uri}s32s32s32s32sQ", 
                    data[8:][:4*3+len_name+len_symbol+len_uri+32*4+8]
                )
                name,symbol,uri = [x.decode('utf-8') for x in [name,symbol,uri]]
                mint,curve,user,creator = [base58.b58encode(x).decode('utf-8') for x in [mint,curve,user,creator]]
                on_token_creation(signature, slot, name, symbol, uri, mint, curve, user, creator)
        
        elif sub_id == sub_id_swap and not swap_received:
            swaps = filter(
                lambda x: x[0:8].hex() == "bddb7fd34ee661ee",
                program_data_logs
            )
            for data in swaps:
                mint, sol_amount, token_amount, is_buy, user, timestamp, v_sol_reserves, v_token_reserves, r_sol_reserves, r_token_reserves = struct.unpack('<32sQQB32sQQQQQ', data[8:129])
                mint,user = [base58.b58encode(x).decode('utf-8') for x in [mint,user]]
                on_swap(signature, slot, timestamp, mint, user, is_buy, sol_amount, token_amount, v_sol_reserves, v_token_reserves, r_sol_reserves, r_token_reserves)
    
    await ws.close()

asyncio.run(runAsync())
