import discord
from discord import app_commands
from discord.ext import tasks
import json
import os
import math
import pickle
import datetime
import requests
from dotenv import load_dotenv
load_dotenv()
dotenv_path = os.path.join(os.path.dirname(__file__), '.env')
load_dotenv(dotenv_path)

MY_GUILD = discord.Object(id=1121061974944518244)

class MyClient(discord.Client):
  def __init__(self, *, intents: discord.Intents):
    super().__init__(intents=intents)
    self.tree = app_commands.CommandTree(self)

  async def setup_hook(self):
    self.tree.copy_global_to(guild=MY_GUILD)
    await self.tree.sync(guild=MY_GUILD)

intents = discord.Intents.default()
client = MyClient(intents=intents)
settings = {
    "channel": 0,
    "registeredUser": [],
}

JST = datetime.timezone(datetime.timedelta(hours=+9), 'JST')

if os.path.exists('settings.pkl'):
  with open('settings.pkl', 'rb') as f:
    settings = pickle.load(f)
    print(f'Restored Settings:\n{json.dumps(settings, indent=2)}')

@client.event
async def on_ready():
  print(f'Logged in as {client.user} (ID: {client.user.id})')
  print('------')
  schedule.start()

@client.tree.command()
async def channel(interaction: discord.Interaction):
  """メッセージを送信するチャンネルを設定します。"""
  print(f'Channel Selected: {interaction.channel.id}')
  settings["channel"] = interaction.channel.id
  with open('settings.pkl', 'wb') as f:
    pickle.dump(settings, f)
  await interaction.response.send_message('チャンネルを設定しました。')

@client.tree.command()
async def register(interaction: discord.Interaction, users: str):
  """AtCoderのユーザー名を登録します。カンマ区切りで複数人指定できます。"""
  for user in users.split(","):
    print(f'User Registered: {user.strip()}')
    settings["registeredUser"].append(user.strip())
  with open('settings.pkl', 'wb') as f:
    pickle.dump(settings, f)
  await interaction.response.send_message(f'ユーザー({users})を登録しました。')

@client.tree.command()
async def unregister(interaction: discord.Interaction, username: str):
  """AtCoderのユーザー名を登録解除します。"""
  print(f'User Unregistered: {username}')
  settings["registeredUser"].remove(username)
  with open('settings.pkl', 'wb') as f:
    pickle.dump(settings, f)
  await interaction.response.send_message(f'ユーザー({username})を登録解除しました。')

@client.tree.command()
async def registerlist(interaction: discord.Interaction):
  """登録されているユーザーの一覧を表示します。"""
  await interaction.response.send_message(f'登録されているユーザーの一覧です。\n{", ".join(settings["registeredUser"])}')

time = datetime.time(hour=0, minute=0, second=0, tzinfo=JST)
@tasks.loop(time=time)
async def schedule():
  await check()
  
@client.tree.command()
async def run(interaction: discord.Interaction):
  await interaction.response.defer()
  await check()
  await interaction.followup.send("完了!")

async def check():
  channel = client.get_channel(settings["channel"])
  searchTime = int((datetime.datetime.now(JST) - datetime.timedelta(days=1)).timestamp())

  problemModels = {}
  url = "https://kenkoooo.com/atcoder/resources/problem-models.json"
  print(f'Accessing: {url}')
  problemModelsResponse = requests.get(url)
  if problemModelsResponse.status_code == 200:
    print("Success!")
    problemModels = problemModelsResponse.json()
  else:
    await channel.send("Difficultyデータにアクセスできませんでした。")
    print("Failure!")
    return
  
  problemInformations = {}
  url = "https://kenkoooo.com/atcoder/resources/problems.json"
  print(f'Accessing: {url}')
  problemInformationsResponse = requests.get(url)
  if problemInformationsResponse.status_code == 200:
    print("Success!")
    problemInformations = problemInformationsResponse.json()
  else:
    await channel.send("問題の情報データにアクセスできませんでした。")
    print("Failure!")
    return

  isMessageSent = False
  for user in settings["registeredUser"]:
    submissions = []
    url = f'https://kenkoooo.com/atcoder/atcoder-api/v3/user/submissions?user={user}&from_second={searchTime}'
    print(f'Accessing: {url}')
    submissionsResponse = requests.get(url)
    if submissionsResponse.status_code == 200:
      submissions = submissionsResponse.json()
      print(f'Result:\n{json.dumps(submissions, indent=2)}')
    else:
      await channel.send(f'{user}: 提出データにアクセスできませんでした。')
      print(f'Failure!')
      continue

    accepts = list(filter(lambda x: x["result"] == "AC", submissions))
    if accepts == []:
      print("No Accepts")
      continue
    else:
      isMessageSent = True
      embed = discord.Embed(title=f'{user}さんが昨日ACした問題', url=f'https://atcoder.jp/users/{user}')
      highestDiff = 0
      for accept in accepts:
        embed.add_field(name=getTitle(problemInformations, accept), value=f'Diff: {getDifficultyAndRateColor(problemModels, accept)} | [提出]({getSubmissionURL(accept)})', inline=True)
        if (getDifficulty(problemModels, accept) > highestDiff):
          highestDiff = getDifficulty(problemModels, accept)
      embed.color = getRateColor(highestDiff)["color"]
      await channel.send(embed=embed)
  if isMessageSent == False:
    await channel.send("今日は誰もACしませんでした。")
  print("Message sent successfully")

def getTitle(problemInformations, problem):
  return next(filter(lambda x: x["id"] == problem["problem_id"], problemInformations), {}).get("title", problem["problem_id"])

def getSubmissionURL(problem):
  return(f'https://atcoder.jp/contests/{problem["contest_id"]}/submissions/{problem["id"]}')

def getDifficulty(problemModels, problem):
  difficulty = problemModels.get(problem["problem_id"], {}).get("difficulty", "不明")
  if (difficulty == "不明"):
    return(difficulty)
  else:
    difficulty = round(difficulty if difficulty >= 400 else 400 / math.exp(1.0 - difficulty / 400))
    return(difficulty)

def getRateColor(difficulty):
  if (type(difficulty) != int):
    return("不明")
  colors = {
    2800: {
      "name": "赤",
      "color": 0xff0000,
    },
    2400: {
      "name": "橙",
      "color": 0xff8000,
    },
    2000: {
      "name": "黄",
      "color": 0xc0c000,
    },
    1600: {
      "name": "青",
      "color": 0x0000ff,
    },
    1200: {
      "name": "水",
      "color": 0x00c0c0,
    },
    800: {
      "name": "緑",
      "color": 0x008000,
    },
    400: {
      "name": "茶",
      "color": 0x804000,
    },
    0: {
      "name": "灰",
      "color": 0x808080,
    },
  }
  for rate in colors.keys():
    if difficulty >= rate:
      return(colors[rate])
  return({
    "name": "不明",
    "color": 0x000000,
  })

def getDifficultyAndRateColor(problemModels, problem):
  difficulty = getDifficulty(problemModels, problem)
  if (difficulty == "不明"):
    return(difficulty)
  else:
    return(f'{difficulty}({getRateColor(difficulty)["name"]})')

client.run(os.getenv("TOKEN"))
