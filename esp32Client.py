# CLIENTE PARA SERVIDOR GATEWAY_MANAGER V1.1

from machine import Pin, ADC, PWM
import urequests
import machine
import time
import network
import uasyncio
import sys


class GateawayManager:

    def __init__(self, ssid='', password=''):

        self.status_led = Pin(14, Pin.OUT)
        self.status_led.value(0)

        self.server = "http://mikelv.pythonanywhere.com"
        self.device_id = "esp32_01"

        self._pin_actions = {}

        self._ssid = ssid
        self._password = password

        # ===== intervals =====
        self.ask_command_interval = 2000
        self.send_adc_interval = 3000

        # ===== http =====
        self.http_timeout = 2

        self.buffer_lock = uasyncio.Lock()

        self.DEBOUNCE_MS = 100

        self._buttons = {}

        self.isGraphActive = False

        # ===== action handlers =====
        self.actions_handlers = {
            'toggle_led': self.toggle_led,
            'set_pwm': self.set_pwm,
            'graph_is_active': self.active_graph,
            'graph_is_inactive': self.deactivate_graph
        }

        self._net = None
        self._config_network()

    # =========================================================
    # NETWORK
    # =========================================================

    def _config_network(self):

        network.WLAN(network.AP_IF).active(False)

        net = network.WLAN(network.STA_IF)

        net.active(False)
        net.active(True)

        time.sleep(1)

        print("-" * 50)
        print("[+] Connecting to:", self._ssid)
        print("-" * 50)

        net.connect(self._ssid, self._password)

        start = time.time()

        while not net.isconnected():

            if time.time() - start > 10:
                print("[!] WiFi timeout")
                machine.soft_reset()

            time.sleep(0.5)

        print("[+] Connected")
        print("[+] IP:", net.ifconfig()[0])

        self._net = net

    # =========================================================
    # PIN REGISTRY
    # =========================================================

    def register_pin(self, pin_num, action_type, pwm_freq=None):

        if pin_num in self._pin_actions:
            self._pin_actions.pop(pin_num)

        if action_type == 'out':

            self._pin_actions[pin_num] = {
                'type': 'out',
                'obj': Pin(pin_num, Pin.OUT)
            }

        elif action_type == 'ADC':

            self._pin_actions[pin_num] = {
                'type': 'ADC',
                'obj': ADC(Pin(pin_num))
            }

        elif action_type == 'PWM':

            pwm = PWM(Pin(pin_num))

            if pwm_freq is not None:
                pwm.freq(pwm_freq)

            pwm.duty(0) #duty inicial

            self._pin_actions[pin_num] = {
                'type': 'PWM',
                'obj': pwm
            }

    # =========================================================
    # BUTTONS
    # =========================================================

    def register_button(self, pin_num, pull=Pin.PULL_DOWN):

        pin = Pin(pin_num, Pin.IN, pull)

        self._buttons[pin_num] = {
            'obj': pin,
            'active_low': (pull == Pin.PULL_UP),
            'last_state': pin.value(),
            'debounce_until': 0
        }

    # =========================================================
    # ACTIONS
    # =========================================================

    def toggle_led(self, pin=None, value=None):

        try:

            if pin is None:
                pin = 11

            pin_obj = self._pin_actions[pin]['obj']

            if value is not None:
                pin_obj.value(1 if value else 0)
            else:
                pin_obj.value(not pin_obj.value())

            return True

        except Exception as e:
            print("[!] toggle_led:", e)
            return False

    def set_pwm(self, pin=None, value=None):

        try:

            if pin is None or value is None:
                return False

            pwm_obj = self._pin_actions[pin]['obj']

            duty = int((value / 100.0) * 1023)

            pwm_obj.duty(duty)

            return True

        except Exception as e:
            print("[!] set_pwm:", e)
            return False

    def active_graph(self, pin=None, value=None):

        self.isGraphActive = True
        print("[+] Graph active")

        return True

    def deactivate_graph(self, pin=None, value=None):

        self.isGraphActive = False
        print("[+] Graph inactive")

        return True

    # =========================================================
    # HEARTBEAT
    # =========================================================

    async def heartbeat(self):

        while True:

            self.status_led.value(1)
            await uasyncio.sleep_ms(100)

            self.status_led.value(0)
            await uasyncio.sleep_ms(2000)

    # =========================================================
    # BUTTON PROCESSOR
    # =========================================================

    async def btn_processor(self):

        while True:

            now = time.ticks_ms()

            for pin_num, obj in self._buttons.items():

                pin = obj['obj']

                current = pin.value()
                last = obj['last_state']

                if current == last:
                    continue

                if time.ticks_diff(now, obj['debounce_until']) < 0:
                    continue

                obj['last_state'] = current

                obj['debounce_until'] = time.ticks_add(
                    now,
                    self.DEBOUNCE_MS
                )

                active_low = obj['active_low']

                if active_low:
                    event = 'pressed' if current == 0 else 'released'
                else:
                    event = 'pressed' if current == 1 else 'released'

                print(f"[BTN] GPIO{pin_num} {event}")

                route = f"{self.server}/api/btn/{event}"

                resp = None

                try:

                    resp = urequests.post(
                        route,
                        json={},
                        timeout=self.http_timeout
                    )

                    print("[BTN] sent:", resp.status_code)

                except Exception as e:

                    print("[BTN] error:", e)

                finally:

                    if resp:
                        resp.close()

            await uasyncio.sleep_ms(10)

    # =========================================================
    # ADC READER
    # =========================================================

    async def adc_reader(self):
        route_adc = f"{self.server}/api/adc"

        while True:

            if self.isGraphActive:
                resp = None

                try:

                    adc = self._pin_actions[16]['obj']

                    voltage = adc.read_uv() * 0.000001

                    print("[ADC]", voltage)
                    
                    # -- envia al servidor
                    resp = urequests.post(
                        f"{route_adc}/{str(voltage)}",
                        json={
                            "voltage": voltage
                        },
                        timeout=self.http_timeout
                    )
                    
                    if resp.status_code == 200:
                        print("[ADC] sent")
                        
                    else:
                        print("[ADC] server error:", resp.status_code)

                except Exception as e:

                    print("[ADC] error:", e)
                
                finally:
                    if resp:
                        resp.close()

            await uasyncio.sleep_ms(self.send_adc_interval)

    # =========================================================
    # COMMAND LISTENER
    # =========================================================

    async def http_server_listener(self):

        print("-" * 50)
        print("[+] Listening server...")
        print("-" * 50)

        route_get_command = f"{self.server}/api/queue/next"
        route_ack = f"{self.server}/api/queue/ack"

        while True:

            resp = None

            try:

                if not self._net.isconnected():

                    print("[!] Reconnecting WiFi...")
                    self._config_network()

                # ===== GET COMMAND =====

                resp = urequests.get(
                    route_get_command,
                    timeout=self.http_timeout
                )

                # ===== COMMAND RECEIVED =====

                if resp.status_code == 200:

                    data = resp.json()

                    print("[RX]", data)

                    cmd_id = data.get("id")
                    pin = data.get("pin")
                    cmd = data.get("cmd")
                    value = data.get("value")

                    if cmd in self.actions_handlers:

                        result = self.actions_handlers[cmd](
                            pin=pin,
                            value=value
                        )

                        # ===== SEND ACK =====

                        if result and cmd_id is not None:

                            ack_resp = None

                            try:

                                ack_resp = urequests.post(
                                    route_ack,
                                    json={"id": cmd_id},
                                    timeout=self.http_timeout
                                )

                                print("[ACK]", cmd_id)

                            except Exception as e:

                                print("[ACK ERROR]", e)

                            finally:

                                if ack_resp:
                                    ack_resp.close()

                elif resp.status_code == 204:

                    pass

                else:

                    print("[SERVER]", resp.status_code)

            except Exception as e:

                print("[HTTP ERROR]", e)

            finally:

                if resp:
                    resp.close()

            await uasyncio.sleep_ms(
                self.ask_command_interval
            )

    # =========================================================
    # MAIN
    # =========================================================

    async def run(self):

        print("[+] Starting tasks")

        await uasyncio.gather(
            self.heartbeat(),
            self.btn_processor(),
            self.http_server_listener(),
            self.adc_reader()
        )


# =============================================================
# MAIN
# =============================================================

if __name__ == "__main__":

    SSID = "SOLUCIONESIT6190"
    PASS = "756uR394"

    app = GateawayManager(
        ssid=SSID,
        password=PASS
    )

    app.register_pin(16, 'ADC')
    app.register_pin(11, 'PWM')
    app.register_pin(46, 'out')
    app.register_button(7)

    try:

        uasyncio.run(app.run())

    except Exception as e:

        sys.print_exception(e)

    except KeyboardInterrupt:

        app.status_led.value(0)
        print("bye :)")