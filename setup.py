#!/usr/bin/python3
# coding=utf-8
# File name   : setup.py
# Author      : Adeept

import os
import subprocess

def run_command(cmd=""):
    process = subprocess.Popen(
        cmd,
        shell=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT
    )
    result = process.stdout.read().decode("utf-8")
    status = process.wait()
    return status, result


def get_user_info():
    command = (
        "u=\"${SUDO_USER:-$(who -m | awk '{ print $1 }')}\"; "
        "h=$(getent passwd \"$u\" | cut -d: -f6); "
        "echo \"$u:$h\""
    )
    _, output = run_command(command)

    if ":" in output:
        return output.strip().split(":", 1)
    return None, None


def check_rpi_model():
    _, result = run_command(
        "cat /sys/firmware/devicetree/base/model | awk '{print $3}'"
    )
    result = result.strip()

    if result == "3":
        return 3
    elif result == "4":
        return 4
    elif result == "5":
        return 5
    return None


def check_raspbian_version():
    _, result = run_command(
        "cat /etc/debian_version | awk -F. '{print $1}'"
    )
    return int(result.strip())


def check_os_bit():
    _, result = run_command("getconf LONG_BIT")
    return int(result.strip())


def check_systemctl_service(service_name):
    result = subprocess.run(
        ["systemctl", "is-active", service_name],
        capture_output=True,
        text=True
    )
    return result.stdout.strip() == "active"


def install_apt_packages():
    commands = [
        "sudo apt-get update",
        "sudo apt-get install -y i2c-tools",
        "sudo apt-get install -y python3-smbus",
        "sudo apt-get install -y python3-gpiozero ",
        "sudo apt-get install -y python3-picamera2",
        "sudo apt-get install -y python3-opencv",
        "sudo apt-get install -y opencv-data",
    ]

    for attempt in range(3):
        success = True
        for command in commands:
            return_code, output = run_command(command)
            print(f"\n===== Running: {command} =====")
            print(output)

            if return_code != 0:
                print("Error running installation step [apt]")
                success = False
                break
        if success:
            return True
    return False


def install_pip_packages():
    commands = [
        "sudo pip3 install Adafruit-Blinka-Raspberry-Pi-PWM "
                            "adafruit-circuitpython-motor "
                            "adafruit-circuitpython-pca9685 "
                            "adafruit-circuitpython-busdevice "
                            "adafruit-circuitpython-ssd1306 "
                            "adafruit-circuitpython-ads7830 --break-system-packages",

        "sudo pip3 install pillow luma.oled mpu6050-raspberrypi spidev --break-system-packages",
        "sudo pip3 install flask_cors flask --break-system-packages",
        "sudo pip3 install numpy imutils pyzmq pybase64 psutil --break-system-packages",
        "sudo pip3 install websockets --break-system-packages",
        "sudo pip3 install sherpa-onnx sherpa-onnx-bin --break-system-packages"
    ]

    if check_rpi_model() == 5:
        print("Raspberry Pi 5 detected, installing Adafruit-Blinka-Raspberry-Pi5-Neopixel library...")
        commands.append("sudo pip3 install Adafruit-Blinka-Raspberry-Pi5-Neopixel --break-system-packages")

    for attempt in range(3):
        success = True
        for command in commands:
            return_code, output = run_command(command)
            print(f"\n===== Running: {command} =====")
            print(output)
            if return_code != 0:
                print("Error running installation step [pip3]")
                success = False
                break
        if success:
            return True
    return False


def install_wifi_service(user_home, setup_path):
    service_name = "wifi-hotspot-manager.service"
    if check_systemctl_service(service_name):
        return
    script_path = os.path.join(user_home, "wifi_hotspot_manager.sh")
    run_command(f"sudo cp {setup_path}/wifi_hotspot_manager.sh {script_path}")
    run_command(f"sudo chmod +x {script_path}")

    service_content = f"""[Unit]
Description=WiFi and Hotspot Manager Service
After=network.target NetworkManager.service
Wants=NetworkManager.service

[Service]
Type=oneshot
ExecStart={script_path}
User=root
RemainAfterExit=yes

[Install]
WantedBy=multi-user.target
"""

    service_file_path = f"/etc/systemd/system/{service_name}"
    try:
        with open(service_file_path, "w") as file:
            file.write(service_content)
        print(f"Service file created: {service_file_path}")
        os.chmod(service_file_path, 0o644)
        subprocess.run(["sudo", "systemctl", "daemon-reload"], check=True)
        subprocess.run(["sudo", "systemctl", "enable", service_name], check=True)
        print(f"Service {service_name} has been enabled and started")
    except subprocess.CalledProcessError as error:
        print(f"Command execution failed: {error}")
    except Exception as error:
        print(f"An error occurred: {error}")


def install_robot_service(user_home, setup_path):
    service_name = "Adeept_Robot.service"
    if check_systemctl_service(service_name):
        return
    startup_script = os.path.join(user_home, "startup.sh")
    robot_script = os.path.join(setup_path, "Server", "WebServer.py")

    try:
        run_command(f"sudo touch {startup_script}")
        with open(startup_script, "w") as file:
            file.write(f"#!/bin/sh\nsleep 5\nsudo python3  {robot_script}")
    except Exception:
        pass
    run_command(f"sudo chmod +x {startup_script}")

    service_content = f"""[Unit]
Description=Auto-start robot control script
After=wifi-hotspot-manager.service

[Service]
Type=simple
User=root
WorkingDirectory={user_home}
ExecStart={startup_script}
Restart=no

[Install]
WantedBy=multi-user.target
"""

    service_file_path = f"/etc/systemd/system/{service_name}"
    try:
        with open(service_file_path, "w") as file:
            file.write(service_content)
        print(f"Service file created: {service_file_path}")
        os.chmod(service_file_path, 0o644)
        subprocess.run(["sudo", "systemctl", "daemon-reload"], check=True)
        subprocess.run(["sudo", "systemctl", "enable", service_name], check=True)
        print(f"Service {service_name} has been enabled and started")
    except subprocess.CalledProcessError as error:
        print(f"Command execution failed: {error}")
    except Exception as error:
        print(f"An error occurred: {error}")


def main():
    username, user_home = get_user_info()

    setup_path = os.path.dirname(os.path.realpath(__file__))

    print(f"curpath: {setup_path}")
    print(f"username: {username}")
    print(f"user_home: {user_home}")

    install_apt_packages()
    install_pip_packages()

    install_wifi_service(user_home, setup_path)
    install_robot_service(user_home, setup_path)

    print("The program in Raspberry Pi has been installed, disconnected and restarted.\n"
        "You can now power off the Raspberry Pi to install the camera and driver board (Robot HAT).\n"
        "After turning on again, the Raspberry Pi will automatically run the program to set the servos port signal to the middle position, which is convenient for mechanical assembly."
    )

    print("restarting...")
    run_command("sudo reboot")

if __name__ == "__main__":
    main()