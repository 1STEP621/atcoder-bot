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
from typing import Union
from setproctitle import setproctitle

load_dotenv()
dotenv_path = os.path.join(os.path.dirname(__file__), '.env')
load_dotenv(dotenv_path)
setproctitle('AtCoderBot')

JST = datetime.timezone(datetime.timedelta(hours=+9), 'JST')
class Color:
  def __init__(self, name: str, color: int):
    self.name = name
    self.color = color
class Settings:
  def __init__(self, channel: str, registeredUser: list[str]):
    self.channel = channel
    self.registeredUser = registeredUser

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

settings = Settings(0, [])
if os.path.exists('settings.pkl'):
  with open('settings.pkl', 'rb') as f:
    settings = pickle.load(f)
    assert isinstance(settings, Settings)
    print(f'Restored Settings:\n{vars(settings)}')

@client.event
async def on_ready():
  print(f'Logged in as {client.user} (ID: {client.user.id})')
  print('------')
  schedule.start()

@client.tree.command()
async def channel(interaction: discord.Interaction):
  """メッセージを送信するチャンネルを設定します。"""
  print(f'Channel Selected: {interaction.channel.id}')
  settings.channel = interaction.channel.id
  with open('settings.pkl', 'wb') as f:
    pickle.dump(settings, f)
  await interaction.response.send_message('チャンネルを設定しました。')

@client.tree.command()
async def register(interaction: discord.Interaction, usernames: str):
  """AtCoderのユーザー名を登録します。カンマ区切りで複数人指定できます。"""
  for user in usernames.split(","):
    print(f'User Registered: {user.strip()}')
    settings.registeredUser.append(user.strip())
  with open('settings.pkl', 'wb') as f:
    pickle.dump(settings, f)
  await interaction.response.send_message(f'ユーザー({usernames})を登録しました。')

@client.tree.command()
async def unregister(interaction: discord.Interaction, username: str):
  """AtCoderのユーザー名を登録解除します。"""
  print(f'User Unregistered: {username}')
  settings.registeredUser.remove(username)
  with open('settings.pkl', 'wb') as f:
    pickle.dump(settings, f)
  await interaction.response.send_message(f'ユーザー({username})を登録解除しました。')

@client.tree.command()
async def registerlist(interaction: discord.Interaction):
  """登録されているユーザーの一覧を表示します。"""
  await interaction.response.send_message(f'登録されているユーザーの一覧です。\n{", ".join(settings.registeredUser)}')
  
@client.tree.command()
async def run(interaction: discord.Interaction):
  """即時実行します。"""
  await interaction.response.defer()
  await check()
  await interaction.followup.send("完了！")

time = datetime.time(hour=0, minute=0, second=0, tzinfo=JST)
@tasks.loop(time=time)
async def schedule():
  await check()

async def check():
  channel = client.get_channel(settings.channel)
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

  embeds = []
  for user in settings.registeredUser:
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
      embed = discord.Embed(title=f'{user}さんが昨日ACした問題', url=f'https://atcoder.jp/users/{user}')
      highestDiff = 0
      for accept in accepts:
        informations = ' | '.join([
          f'Diff: {getDifficulty(problemModels, accept) or "不明"}({getRateColor(getDifficulty(problemModels, accept)).name})',
          f'{getLanguage(accept)}',
          f'[提出]({getSubmissionURL(accept)})'
        ])
        embed.add_field(name=getTitle(problemInformations, accept), value=informations, inline=False)
        if ((getDifficulty(problemModels, accept) or 0) > highestDiff):
          highestDiff = getDifficulty(problemModels, accept)
      embed.color = getRateColor(highestDiff).color
      embeds.append(embed)
  if embeds == []:
    await channel.send("昨日は誰もACしませんでした。")
  else:
    await channel.send(embeds=embeds)
  print("Message sent successfully")

def getTitle(problemInformations, problem) -> str:
  return next(filter(lambda x: x["id"] == problem["problem_id"], problemInformations), {}).get("title", problem["problem_id"])

def getSubmissionURL(problem) -> str:
  return(f'https://atcoder.jp/contests/{problem["contest_id"]}/submissions/{problem["id"]}')

def getLanguage(problem) -> str:
  return(problem["language"])

def getDifficulty(problemModels, problem) -> Union[int, None]:
  difficulty = problemModels.get(problem["problem_id"], {}).get("difficulty", None)
  if (difficulty is None):
    return(difficulty)
  else:
    difficulty = round(difficulty if difficulty >= 400 else 400 / math.exp(1.0 - difficulty / 400))
    return(difficulty)

def getRateColor(difficulty : Union[int, None]) -> Color:
  if (difficulty is None):
    return(Color("不明", 0x000000))
  colors = {
    2800: Color("赤", 0xff0000),
    2400: Color("橙", 0xff8000),
    2000: Color("黄", 0xc0c000),
    1600: Color("青", 0x0000ff),
    1200: Color("水", 0x00c0c0),
    800: Color("緑", 0x008000),
    400: Color("茶", 0x804000),
    0: Color("灰", 0x808080),
  }
  for rate in colors.keys():
    if difficulty >= rate:
      return(colors[rate])
  return(Color("不明", 0x000000))

client.run(os.getenv("TOKEN"))
