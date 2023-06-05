import asyncio
from fastapi import FastAPI
import logging

from riotee.packet_model import *
from riotee.transceiver import Transceiver


class PacketDatabase(object):
    """Stores received packets until they are retrieved over the API."""

    def __init__(self) -> None:
        self.__db = dict()

    def add(self, pkt: PacketApiReceive):
        try:
            self.__db[pkt.dev_id].append(pkt)
        except KeyError:
            self.__db[pkt.dev_id] = [pkt]

    def get_devices(self):
        return list(self.__db.keys())

    def __getitem__(self, dev_id):
        return self.__db[dev_id]


async def receive_loop(tcv: Transceiver, db: PacketDatabase):
    while True:
        pkt = await tcv.read_packet()
        db.add(pkt)
        logging.debug(f"Got packet from {pkt.dev_id} with ID {pkt.pkt_id} @{pkt.timestamp}")


tcv = Transceiver()
db = PacketDatabase()
app = FastAPI()


@app.get("/")
async def get_root():
    return "Welcome to the Riotee Gateway!"


@app.get("/devices")
async def get_devices():
    return db.get_devices()


@app.get("/in/all/size")
async def get_all_queue_size():
    n_tot = 0
    for dev_id in db.get_devices():
        n_tot += len(db[dev_id])
    return n_tot


@app.get("/in/all/all")
async def get_all_packets(dev_id: bytes):
    pkts = list()
    for dev_id in db.get_devices():
        pkts += db[dev_id]
    return pkts


@app.delete("/in/all/all")
async def delete_all_packets(dev_id: bytes):
    pkts = list()
    for dev_id in db.get_devices():
        db[dev_id] = list()


@app.get("/in/{dev_id}/size")
async def get_queue_size(dev_id: bytes):
    return len(db[dev_id])


@app.get("/in/{dev_id}/all")
async def get_all_dev_packets(dev_id: bytes):
    return db[dev_id]


@app.delete("/in/{dev_id}/all")
async def delete_all_devpackets(dev_id: bytes):
    db[dev_id] = list()


@app.get("/in/{dev_id}/{index}")
async def get_packet(dev_id: bytes, index: int):
    return db[dev_id][index]


@app.delete("/in/{dev_id}/{index}")
async def delete_packet(dev_id: bytes, index: int):
    del db[dev_id][index]


@app.post("/out/{dev_id}")
async def post_packet(dev_id: bytes, packet: PacketApiSend):
    pkt_tcv = PacketTransceiverSend.from_PacketApiSend(packet, dev_id)
    tcv.send_packet(pkt_tcv)
    return packet


@app.on_event("startup")
async def startup_event():
    await tcv.__enter__()
    asyncio.create_task(receive_loop(tcv, db))


@app.on_event("shutdown")
def shutdown_event():
    tcv.__exit__()