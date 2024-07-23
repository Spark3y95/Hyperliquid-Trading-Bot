from typing import Optional, List
import pandas as pd
import pandas_ta as ta
import ccxt
from execution_service import HyperLiquidExecutionService
from discord import SyncWebhook
import json
import threading
import time

lock = threading.Lock()

class Asset:
    def __init__(self, id : int, rawAssetName : str, tf : str, hyperliquidBot : HyperLiquidExecutionService, is_longStrat : bool ):
        self.id = id
        self.coinpair = rawAssetName.upper() + "USDT"
        self.rawAssetName = rawAssetName.upper()
        self.tf = tf
       
        self.setSl = False
        self.is_longStrat = is_longStrat
        
        self.history = None
        self.hmaTrend = None
        self.nextUpdate = None
        self.leverage = None
        self.exist = True
        self.hyperLiquidBot = hyperliquidBot 
        self.txn_USDTAmount = 20
        self.hmalength = 96
        self.TotalAccountValue = None
        
        
        configFile = open("config.json", "r")
        configFile = configFile.read()
        
        exchange = json.loads(configFile)["exchange"]
        if exchange == "binance":
            self.exchange = ccxt.binance()
        elif exchange == "bybit":
            self.exchange = ccxt.bybit()
        else:
            print("Invalid exchange in config.json")
            return
        
        
        
        webhookUrl = json.loads(configFile)["webhook"]
        self.webhook = SyncWebhook.from_url(webhookUrl)
        
        print("Asset loaded")
        
        # res = self.hyperLiquidBot.generate_order(self.rawAssetName, self.txn_USDTAmount, "b")
        # print(res)
        # time.sleep(5)
        # res = self.hyperLiquidBot.close_position(self.rawAssetName)

    def set_sl(self):
        self.setSl = True

    
    def change_txn_amount(self, amount):
        print(f"Changing Ape Amount for {self.rawAssetName} to {amount}")
        self.txn_USDTAmount = amount
        return self.txn_USDTAmount
        
        
    def get_historical_data(self):
        time.sleep(5) 
        
        retry = 0
        data = None
        while retry < 3:
            try:
                data = self.exchange.fetch_ohlcv(self.coinpair, self.tf, limit=200)
                break
            except Exception as e:
                print(e)
                retry += 1
                time.sleep(5)

        if retry == 3:
            self.webhook.send(f"@everyone Error fetching data for {self.coinpair}")
            self.exist = False
            return
        
        
        
        data = [[self.exchange.iso8601(candle[0])] + candle[1:] for candle in data]
        header = ['Timestamp', 'Open', 'High', 'Low', 'Close', 'Volume']
        df = pd.DataFrame(data, columns=header)
        self.history = df
        
        lastTimestamp = df["Timestamp"].iloc[-1]
        
        nextTimestamp = None
        if self.tf == "1m":
            nextTimestamp = pd.Timestamp(lastTimestamp) + pd.Timedelta(minutes=1)
            
        if self.tf == "15m":
            nextTimestamp = pd.Timestamp(lastTimestamp) + pd.Timedelta(minutes=15)
        
        if self.tf == "1h":
            nextTimestamp = pd.Timestamp(lastTimestamp) + pd.Timedelta(hours=1)

        if self.tf == "4h":
            nextTimestamp = pd.Timestamp(lastTimestamp) + pd.Timedelta(hours=4)

        if self.tf == "1d":
            nextTimestamp = pd.Timestamp(lastTimestamp) + pd.Timedelta(days=1)

        
        self.nextUpdate = nextTimestamp.replace(tzinfo=None)            


    def get_slPrice(self) -> float:
        limit = 50
        
        if self.tf == '1d':
            limit = 20
        
        history = self.exchange.fetch_ohlcv(self.coinpair, timeframe=self.tf, limit=limit)
        highest_price = max([x[2] for x in history])
        lowest_price = min([x[3] for x in history])
        return lowest_price, highest_price
    
    
    def changehma(self, length : int):
        self.hmalength = length
        self.hmaTrend = None
        self.generateSignal()
        print(f"{self.coinpair} hma changed to {length}")        
        
        
    def generateSignal(self):
        df = self.history
        df["HMA96"] = df.ta.hma(series=df["Close"], length=self.hmalength)
        last = df["HMA96"].iloc[-2] 
        secondLast = df["HMA96"].iloc[-3]
        
        print(f"{self.coinpair} Last: {last} Second Last: {secondLast}")
                        
        if self.hmaTrend == None:
            print(f"{self.coinpair} Initialising HMA Trend as {last > secondLast}")
            self.hmaTrend = last > secondLast
            return
        
        buycondition = last > secondLast and self.hmaTrend == False
        sellcondition = last < secondLast and self.hmaTrend == True
        
        
        lowest = None
        highest = None
        if buycondition or sellcondition:
            if self.setSl:
                lowest, highest = self.get_slPrice()
        
        
        if buycondition:
            print(f"{self.coinpair} Buy Signal on {self.tf} timeframe")
            self.webhook.send(f"@everyone {self.coinpair} Buy Signal on {self.tf} timeframe")
            self.hmaTrend = True
            
            if self.is_longStrat:
                with lock:                    
                    res = self.hyperLiquidBot.generate_order(self.rawAssetName, self.txn_USDTAmount, True, self.setSl, lowest)
                
                
            if not self.is_longStrat:
                with lock:
                    res = self.hyperLiquidBot.close_position(self.rawAssetName)
            
       
        if sellcondition:
            print(f"{self.coinpair} Sell Signal on {self.tf} timeframe")
            self.webhook.send(f"@everyone {self.coinpair} Sell Signal on {self.tf} timeframe")
            self.hmaTrend = False
            
            
            if self.is_longStrat:
                with lock:
                    res = self.hyperLiquidBot.close_position(self.rawAssetName)
            
            
            if not self.is_longStrat:
                with lock:
                    res = self.hyperLiquidBot.generate_order(self.rawAssetName, self.txn_USDTAmount, False, self.setSl, highest)
                    
            
                
            
    # OLD RUN        
    # def run(self):
    #     # # MUST REMOVE THIS
    #     # print(f"{self.coinpair} {self.tf} Running. Sleeping")
    #     # time.sleep(100)
    #     # print(f"{self.coinpair} {self.tf} Waking up")
        
    #     while True:
    #         if self.exist == False:
    #             return
            
    #         self.get_historical_data()
    #         self.generateSignal()
                
    #         timeToSleep = self.nextUpdate - pd.Timestamp.utcnow().replace(tzinfo=None)
    #         timeToSleepSeconds = timeToSleep.total_seconds()
    #         print(f"{self.coinpair} {self.tf} Sleeping for {timeToSleep}")
            
    #         if timeToSleepSeconds > 0:
    #             time.sleep(timeToSleepSeconds)
    #         else:
    #             self.webhook.send(f"@everyone Error: {self.coinpair} {self.tf} Time to sleep is negative. Retrying.")
    #             time.sleep(5)
    
    def run(self):
        self.get_historical_data()
        self.generateSignal()

        while True:
            if self.exist == False:
                return
            
            currenttime = pd.Timestamp.utcnow().replace(tzinfo=None)
            nextupdate = self.nextUpdate
            condition = currenttime >= nextupdate
            
            if condition:
                print(f"{self.coinpair} {self.tf} running inside condition.")
                self.get_historical_data()
                self.generateSignal()
                
            
            diff = nextupdate - currenttime
            diff_seconds = diff.total_seconds()
            
            # ensure that bot wakes up precisely at the next candle
            if diff_seconds < 30:
                if diff_seconds > 0:
                    print(f"{self.coinpair} {self.tf} Sleeping for {diff}")
                    time.sleep(diff_seconds)
                else:
                    print(f"{self.coinpair} {self.tf} Sleeping for 0.1 second")
                    time.sleep(0.1)
            else:
                print(f"{self.coinpair} {self.tf} Sleeping for 20 seconds")
                time.sleep(20)                

class Screener:
    def __init__(self):
        self.assets =  []
        self.idcount = 0
        self.hyperliquidBot : Optional[HyperLiquidExecutionService] = None 
        print("Screener loaded")
        
    def addAsset(self, asset : str, tf : str , sl : int, hma : int, size : float, leverage : int, is_long : bool):
        a = Asset(self.idcount, asset, tf, self.hyperliquidBot, is_long)
        
        if sl == 1:
            a.set_sl()
            
        if size != None:
            a.change_txn_amount(size)
            
        if hma != None:
            a.hmalength = hma
            
        if leverage != None:
            self.hyperliquidBot.set_leverage(a.rawAssetName, leverage) 
            a.leverage = leverage   
        
        t = threading.Thread(target=a.run)
        t.daemon = True
        t.start()
        
        self.assets.append(a)
        self.idcount += 1
    
        
    def removeAsset(self, id):
        for a in self.assets:
            a : Asset
            if a.id == id:
                a.exist = False
                self.assets.remove(a)
                print(f"Removed {a.coinpair}")
                return


# h = HyperLiquidExecutionService()
# s = Screener()
# s.hyperliquidBot = h

# s.addAsset("btc", "1m", 1, 96, 10, 10)
# s.addAsset("sol", "1m", 1, 96, 20, 10)
# s.addAsset("eth", "1m", 1, 96, 20, 10)

# time.sleep(20)

# s.removeAsset(0)
   
# async def infiniteLoop():
#     while True:
#         await asyncio.sleep(100)
        

# asyncio.run(infiniteLoop())