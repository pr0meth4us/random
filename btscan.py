# btscan.py
import asyncio
import objc
import CoreBluetooth
from Foundation import NSObject

class CentralManagerDelegate(NSObject):
    def init(self):
        # Proper Objective-C init call
        self = objc.super(CentralManagerDelegate, self).init()
        if self is None:
            return None

        # Create central manager and set this object as delegate
        self.manager = CoreBluetooth.CBCentralManager.alloc().initWithDelegate_queue_options_(
            self, None, None
        )
        return self

    # Called when Bluetooth state changes
    def centralManagerDidUpdateState_(self, central):
        state = central.state()
        if state == CoreBluetooth.CBManagerStatePoweredOn:
            print("✅ Bluetooth is ON — scanning for nearby devices...")
            central.scanForPeripheralsWithServices_options_(None, None)
        elif state == CoreBluetooth.CBManagerStatePoweredOff:
            print("❌ Bluetooth is OFF — please turn it on.")
        elif state == CoreBluetooth.CBManagerStateUnsupported:
            print("⚠️ Bluetooth not supported on this Mac.")

    # Called when a device is discovered
    def centralManager_didDiscoverPeripheral_advertisementData_RSSI_(
            self, central, peripheral, advData, rssi
    ):
        name = advData.get(CoreBluetooth.CBAdvertisementDataLocalNameKey, peripheral.name())
        print(f"🔎 Found: {name or 'Unknown'} ({peripheral.identifier()}) RSSI={rssi}")

if __name__ == "__main__":
    delegate = CentralManagerDelegate.alloc().init()

    # Create a new asyncio event loop (Python 3.11+ safe)
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    try:
        loop.run_forever()
    except KeyboardInterrupt:
        print("\n🛑 Scan stopped by user.")
