import psutil

# CPU
def _get_cpu_usage():
    usage = psutil.cpu_percent()

    return {
        "cpu_usage": usage,
        "physical_cores": psutil.cpu_count(logical=False),
        "logical_cores": psutil.cpu_count(logical=True)
    }

def _get_cpu_temp():
    # temp = psutil.cpu_stats()
    pass

# GPU


# MEMORY
def _get_ram_usage():
    memory = psutil.virtual_memory()

    return {
        "total_bytes": memory.total,
        "used_bytes": memory.used,
        "available_bytes": memory.available,
        "usage_percent": memory.percent
    }

# NETWORK
def _get_network_status():
    interface_stats = psutil.net_if_stats()
    interface_addresses = psutil.net_if_addrs()

    interfaces = []

    for name, stats in interface_stats.items():
        addresses = []

        for address in interface_addresses.get(name, []):
            addresses.append(
                {
                    "family": str(address.family),
                    "address": address.address,
                    "netmask": address.netmask,
                    "broadcast": address.broadcast,
                }
            )

        interfaces.append(
            {
                "name": name,
                "is_up": stats.isup,
                "speed_mbps": stats.speed,
                "mtu": stats.mtu,
                "addresses": addresses,
            }
        )

    return {
        "interfaces": interfaces,
    }

# BATTERY
def _get_battery_level():
    battery = psutil.sensors_battery()

    if battery is None:
        return { "battery_available": False }

    seconds_left = battery.secsleft

    if seconds_left in (psutil.POWER_TIME_UNLIMITED, psutil.POWER_TIME_UNKNOWN):
        seconds_left = None

    return {
        "available": True,
        "percent": battery.percent,
        "plugged_in": battery.power_plugged,
        "seconds_left": seconds_left,
    }