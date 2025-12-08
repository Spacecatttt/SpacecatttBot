import asyncio
import io
import os
import re
from io import BytesIO
from typing import Any, Awaitable, Callable, Dict

import aiohttp
from aiogram import Bot, Dispatcher, F, types
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.filters import Command, CommandStart
from aiogram.types import CallbackQuery, Update
from aiogram.utils.keyboard import InlineKeyboardBuilder
from dotenv import load_dotenv
from PIL import Image, ImageDraw, ImageFont, ImageOps, ImageSequence

# --- Load environment variables from .env file ---
load_dotenv()

# --- Configuration Constants ---
TOKEN = os.getenv("TOKEN")
CATAPI = os.getenv("CATAPI")
DOGAPI = os.getenv("DOGAPI")
PROXY_URL = os.getenv("PROXY_URL")


FONT_PATH = "app/font.ttf"
WOMEN_GIF_PATH = "women.gif"
MS_PENIS_GIF_PATH = "ms_penis.gif"
MR_PENIS_STICKER_ID = (
    "CAACAgIAAxkBAAIGjGaqRa866MFM7_2dE8YXCy3FHpxSAAKCMwACd7pgSlDQiqr55dnGNQQ"
)

# API Endpoints
CAT_API_SEARCH_URL = (
    "https://api.thecatapi.com/v1/images/search?limit=1"  # &api_key={CATAPI}"
)
CAT_API_GIF_URL = "https://cataas.com/cat/gif"
DOG_API_SEARCH_URL = (
    f"https://api.thedogapi.com/v1/images/search?limit=1&api_key={DOGAPI}"
)


# Banned users list
banned_users_id = []  # 975425731
session = AiohttpSession(proxy=PROXY_URL)
bot = Bot(TOKEN, session=session)
dp = Dispatcher()


# Middleware для перевірки бану
@dp.update.middleware()
async def database_transaction_middleware(
    handler: Callable[[Update, Dict[str, Any]], Awaitable[Any]],
    event: Update,
    data: Dict[str, Any],
) -> Any:
    if (
        event.message
        and event.message.text
        and event.message.text.startswith("/")
        and event.message.from_user.id in banned_users_id
    ):
        return await event.message.answer("Тобі це не дозволено!")

    return await handler(event, data)


@dp.message(CommandStart())
async def start(message: types.Message):
    await message.answer(
        "Привіт, я створений щоб скидувати фото котів. Напиши /help щоб побачити на що я здатен."
    )


command_list = [
    "/start або /hello - Почати роботу з ботом",
    "/help - Показати список доступних команд",
    "/cat - Отримати фото котика з текстом, якщо він є",
    "/cat_bw - Чорно-білий котик (з текстом або без)",
    "/cat_retro - Ретро котик (з текстом або без)",
    "/gif - Отримати гіфку котика з текстом, якщо він є",
    "/breed - Отримати котика певної породи",
    "/today - Отримати який ти котик сьогодні",
    "/селисьзаїбав - нагадати @V_Vladyslavv та @Vlad888555 щоб вони поселилися",
    "/mrpenis - Отримаити стікер Mr penis",
    "/women - Отримати прекрасну гіфку",
]

command_text = "\n".join(
    [f"{i + 1}. {command}" for i, command in enumerate(command_list)]
)

POPULAR_BREEDS = {
    "Бенгал": "beng",
    "Сфінкс": "sphy",
    "Сіам": "siam",
    "Перс": "pers",
    "Мейн-кун": "mcoo",
    "Регдол": "ragd",
}


@dp.message(Command("help", prefix="!/"))
async def help(message: types.Message):
    await message.answer(f"Ось доступні команди:\n{command_text}", parse_mode="HTML")


async def fetch_image_url(url):
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            data = await response.json()
            CAT_API_SEARCH_URL = data[0]["url"]
            return CAT_API_SEARCH_URL


async def fetch_image(url):
    async with aiohttp.ClientSession() as session:
        async with session.get(url, proxy=PROXY_URL) as response:
            return await response.read()


def textSizing(
    draw: ImageDraw.ImageDraw, text: str, img_size: tuple[int, int]
) -> ImageFont.FreeTypeFont:
    font_size = 10
    max_text_width = 0.8 * img_size[0]
    max_text_height = 0.3 * img_size[1]
    jumpsize = 75

    while jumpsize > 1:
        font = ImageFont.truetype(FONT_PATH, int(round(font_size)))
        _, _, text_width, text_height = draw.textbbox((0, 0), text, font=font)

        if text_width > max_text_width or text_height > max_text_height:
            font_size -= jumpsize
            jumpsize //= 2
        else:
            font_size += jumpsize

        if font_size < 10:
            font_size = 10
            break

    return ImageFont.truetype(FONT_PATH, font_size)


async def addTextOnPhoto(url, text, filter_type: str | None = None):
    # Download the image from the URL
    response = await fetch_image(url)
    img = Image.open(BytesIO(response))

    # FILTER BLOCK
    if filter_type == "bw":
        img = img.convert("L")
    elif filter_type == "retro":
        img_bw = img.convert("L")
        img = ImageOps.colorize(img_bw, black="#402810", white="#f0e0c0")

    draw = ImageDraw.Draw(img)
    # Set the font and initial font size
    text_width, text_height = img.size

    font = textSizing(draw, text, img.size)
    _, _, text_width, text_height = draw.textbbox((0, 0), text, font=font)
    position = ((img.width - text_width) // 2, img.height - text_height - 20)

    # Add text to the image
    draw.text(
        position, text, fill="white", font=font, stroke_width=1, stroke_fill="black"
    )

    # Save the image to a BytesIO buffer
    img_buffer = BytesIO()
    if img.mode == "L":
        img = img.convert("RGB")

    img.save(img_buffer, format="PNG")
    img_buffer.seek(0)  # TODO: check if needed
    return img_buffer.getvalue()


async def addTextToGif(gif_bytes: bytes, text: str) -> bytes:
    gif = Image.open(io.BytesIO(gif_bytes))

    # Find the appropriate font size for the first frame
    frames = []
    first_frame = next(ImageSequence.Iterator(gif))
    draw_first = ImageDraw.Draw(first_frame)
    font = textSizing(draw_first, text, first_frame.size)
    _, _, text_width, text_height = draw_first.textbbox((0, 0), text, font=font)
    position = (
        (first_frame.width - text_width) // 2,
        first_frame.height - text_height - 20,
    )

    for frame in ImageSequence.Iterator(gif):
        frame = frame.convert("RGBA")
        draw = ImageDraw.Draw(frame)
        draw.text(
            position, text, fill="white", font=font, stroke_width=1, stroke_fill="black"
        )
        frames.append(frame)

    output = io.BytesIO()
    frames[0].save(
        output,
        format="GIF",
        save_all=True,
        append_images=frames[1:],
        loop=0,
        disposal=2,
    )
    output.seek(0)
    return output.read()


async def addFilterOnPhoto(url, filter_type: str):
    response = await fetch_image(url)

    img = Image.open(BytesIO(response))
    img = img.convert("L")

    if filter_type == "bw":
        pass
    elif filter_type == "retro":
        img = ImageOps.colorize(img, black="#402810", white="#f0e0c0")

    img_buffer = BytesIO()
    img.save(img_buffer, format="PNG")
    img_buffer.seek(0)

    return img_buffer.getvalue()


async def getCat(message: types.Message, command: str, input_type: str):
    text = message.text.replace(command, "", 1).strip()

    try:
        url = await fetch_image_url(CAT_API_SEARCH_URL)
    except Exception as e:
        print(e)
        await message.reply("Коти втомилися (помилка API), підіть теж відпочиньте.")
        return

    filter_type: str | None = input_type if input_type != "basic" else None
    try:
        if not text:
            if filter_type is not None:
                img_buffer = await addFilterOnPhoto(url, filter_type)
                await bot.send_photo(
                    chat_id=message.chat.id,
                    photo=types.BufferedInputFile(file=img_buffer, filename="cat"),
                )
            else:
                await bot.send_photo(chat_id=message.chat.id, photo=url)
        else:
            img_buffer = await addTextOnPhoto(url, text, filter_type)
            await bot.send_photo(
                chat_id=message.chat.id,
                photo=types.BufferedInputFile(file=img_buffer, filename="cat"),
            )
    except Exception as e:
        print(e)
        await message.reply("Ну піздець і де котик...")


@dp.message(Command("cat", prefix="/"))
async def getCatBasic(message: types.Message):
    return await getCat(message, "/cat", "basic")


@dp.message(Command("cat_bw", prefix="/"))
async def getCatBW(message: types.Message):
    return await getCat(message, "/cat_bw", "bw")


@dp.message(Command("cat_retro", prefix="/"))
async def getCatRetro(message: types.Message):
    return await getCat(message, "/cat_retro", "retro")


@dp.message(Command("gif", prefix="/"))
async def getGifCat(message: types.Message):
    text = message.text.replace("/gif", "", 1).strip()
    try:
        response = await fetch_image(CAT_API_GIF_URL)

        if text:
            response = await addTextToGif(response, text)

        await bot.send_animation(
            chat_id=message.chat.id,
            animation=types.BufferedInputFile(file=response, filename="cat.gif"),
        )

    except Exception as e:
        error = str(e)
        print(error)
        if "Flood control exceeded" in error:
            matches = re.search(r"(\d+)\s*seconds", error)
            await message.reply(
                f"Забагато гіфок? В тг є обмеження, почекай {int(matches.group(1))} секунд"
            )
        else:
            await message.reply("Пу пу пу, гіфки не буде. Спробуй ще раз пізніше.")


@dp.message(Command("today", prefix="/"))
async def todayCat(message: types.Message):
    url = await fetch_image_url(CAT_API_SEARCH_URL)

    try:
        text = f"{message.from_user.first_name} сьогодні"
        img_buffer = await addTextOnPhoto(url, text)
        await bot.send_photo(
            chat_id=message.chat.id,
            photo=types.BufferedInputFile(file=img_buffer, filename="cat"),
        )
    except Exception as e:
        print(e)
        await message.reply("Ти супер котик, але фотки не буде ):")


@dp.message(Command("breed", prefix="/"))
async def get_breeds(message: types.Message):
    """Sends a message with buttons to select a breed."""

    builder = InlineKeyboardBuilder()
    for name, breed_id in POPULAR_BREEDS.items():
        builder.add(
            types.InlineKeyboardButton(
                text=name,
                callback_data=f"breed:{name}:{breed_id}",
            )
        )
    # Arrange buttons in 2 columns
    builder.adjust(2)
    keyboard = builder.as_markup()

    await message.answer("Оберіть породу котика:", reply_markup=keyboard)


@dp.callback_query(F.data.startswith("breed:"))
async def send_breed_cat(callback: CallbackQuery):
    # Get the breed ID from callback_data (e.g., "breed:beng" -> "beng")
    [_, breed_name, breed_id] = callback.data.split(":")
    await callback.answer(f"Шукаю котика ({breed_name})...")

    try:
        api_url = f"{CAT_API_SEARCH_URL}&breed_ids={breed_id}"
        image_url = await fetch_image_url(api_url)

        await callback.message.answer_photo(
            photo=image_url, caption=f"Ось котик породи {breed_name}!"
        )

        # Delete the message with the buttons
        await callback.message.delete()

    except Exception as e:
        print(e)
        await callback.message.answer(
            f"Не вдалося знайти котика породи {breed_name}. Схоже, вони всі сплять."
        )


@dp.message(Command("CAT", prefix="/"))
async def getCAT(message: types.Message):
    try:
        url = await fetch_image_url(CAT_API_SEARCH_URL)
        url2 = await fetch_image_url(CAT_API_SEARCH_URL)
        await message.reply("Не ори на мене. Тримай двох котів!")
        await bot.send_photo(chat_id=message.chat.id, photo=url)
        await bot.send_photo(chat_id=message.chat.id, photo=url2)
    except Exception as e:
        print(e)
        await message.reply("А нєхуй орати на мене, кота не буде.")


@dp.message(Command("Hund", prefix="/"))
async def getHund(message: types.Message):
    text = message.text.replace("/Hund", "", 1).strip()
    try:
        url = await fetch_image_url(DOG_API_SEARCH_URL)
    except Exception as e:
        print(e)
        await message.reply(
            "Собачки пішли спати (помилка API), підіть теж відпочиньте."
        )
        return

    try:
        if not text:
            await bot.send_photo(chat_id=message.chat.id, photo=url)
        else:
            img_buffer = await addTextOnPhoto(url, text)
            await bot.send_photo(
                chat_id=message.chat.id,
                photo=types.BufferedInputFile(file=img_buffer, filename="hund"),
            )
    except Exception as e:
        print(e)
        await message.reply("Ну піздець і де песик...")


@dp.message(Command("селисьзаїбав", prefix="/"))
async def selys(message: types.Message):
    url = await fetch_image_url(CAT_API_SEARCH_URL)
    try:
        text = "@V_Vladyslavv, @Vlad888555 селіться заїбали"
        img_buffer = await addTextOnPhoto(url, text)
        await bot.send_message(
            chat_id=message.chat.id, text="@V_Vladyslavv, @Vlad888555 селіться, заїбали!"
        )
        await bot.send_photo(
            chat_id=message.chat.id,
            photo=types.BufferedInputFile(file=img_buffer, filename="cat"),
        )
    except Exception as e:
        print(e)
        await message.reply("кота не буде, але @V_Vladyslavv, @Vlad888555 селіться, заїбали")


@dp.message(Command("women", prefix="/"))
async def women(message: types.Message):
    try:
        await bot.send_animation(
            chat_id=message.chat.id, animation=types.FSInputFile(path=WOMEN_GIF_PATH)
        )
    except Exception as e:
        print(e)
        await message.reply("Мда, жінка зламала бота")


@dp.message(Command("mrpenis", prefix="/"))
async def mrpenis(message: types.Message):
    try:
        await bot.send_sticker(chat_id=message.chat.id, sticker=MR_PENIS_STICKER_ID)
    except Exception as e:
        print(e)
        await message.reply("Містера Пеніса вже не існує 🕯️")


@dp.message(Command("mspenis", prefix="/"))
async def mspenis(message: types.Message):
    try:
        await bot.send_animation(
            chat_id=message.chat.id, animation=types.FSInputFile(path=MS_PENIS_GIF_PATH)
        )
    except Exception as e:
        print(e)
        await message.reply("Мда, жінка зламала бота")


async def main() -> None:
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
