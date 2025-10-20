import asyncio
import json
import websockets
import base64
import base58
import struct
import sys

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
   
async def runAsync(token_creation_callback, swap_callback):
    ws = await websockets.connect("wss://mainnet.helius-rpc.com/?api-key=9e7ab923-d89b-4506-9b9e-618f58b12ca2")
    sub_id_token_creation = await logsSubscribe(ws, "TSLvdd1pWpHVjahSpsvCXUbgwsL3JAcvokwaKt1eokM")
    sub_id_swap = await logsSubscribe(ws, "6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P")

    while True:
        try:
            data = json.loads(await ws.recv())
        except Exception as e:
            print(f"Something went wrong: {e}")
        result = data["params"]["result"]
        err = result["value"]["err"]
        if err != None:
            continue
        slot = result["context"]["slot"]
        signature = result["value"]["signature"]
        logs = result["value"]["logs"]

        if "Log truncated" in logs:
            pass#print(f"TRUNCATED {signature}")

        program_data_logs = map(
            lambda x: base64.b64decode(x[14:]), 
            filter(lambda x: x[:14]=="Program data: ", logs)
        )
        
        sub_id = data["params"]["subscription"]
        if sub_id == sub_id_token_creation:
            if token_creation_callback == None:
                continue
            # Parse token creations
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
                token_creation_callback(signature, slot, name, symbol, uri, mint, curve, user, creator)
        
        elif sub_id == sub_id_swap:
            if swap_callback == None:
                continue
            # Parse swaps
            swaps = filter(
                lambda x: x[0:8].hex() == "bddb7fd34ee661ee",
                program_data_logs
            )
            for data in swaps:
                mint, sol_amount, token_amount, is_buy, user, timestamp, v_sol_reserves, v_token_reserves, r_sol_reserves, r_token_reserves = struct.unpack('<32sQQB32sQQQQQ', data[8:129])
                mint,user = [base58.b58encode(x).decode('utf-8') for x in [mint,user]]
                swap_callback(signature, slot, timestamp, mint, user, is_buy, sol_amount, token_amount, v_sol_reserves, v_token_reserves, r_sol_reserves, r_token_reserves)

        else:
            print(f"Unknown subscription id: {json.dumps(data)}")

def run(token_creation_callback, swap_callback):
    asyncio.run(runAsync(token_creation_callback, swap_callback))
