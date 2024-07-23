import asyncio
from comm_service import CommunicationService
from execution_service import HyperLiquidExecutionService
from screener_service import Screener
import logging
from memory_profiler import memory_usage
import json

#logging.basicConfig(level=logging.DEBUG)

async def main():
    print("in main")
    screener = Screener()
    discordBot = CommunicationService(None, screener)
        
    # asyncio.create_task(memusage())

    token = json.load(open("config.json"))["token"]
    await discordBot.start(token)
    
# async def memusage():
#     while True:
#         print(memory_usage())
#         await asyncio.sleep(10)
        
asyncio.run(main())