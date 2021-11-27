import html
import re
from telegram import ParseMode, ChatPermissions
from telegram.error import BadRequest
from telegram.ext import Filters
from telegram.utils.helpers import mention_html
from tg_bot.modules.sql.approve_sql import is_approved
import tg_bot.modules.sql.blacklist_sql as sql
from tg_bot import SUDO_USERS, log, dispatcher, spamcheck
from tg_bot.modules.helper_funcs.chat_status import user_admin, user_not_admin
from tg_bot.modules.helper_funcs.extraction import extract_text
from tg_bot.modules.helper_funcs.misc import split_message
from tg_bot.modules.log_channel import loggable
from tg_bot.modules.warns import warn
from tg_bot.modules.helper_funcs.string_handling import extract_time
from tg_bot.modules.connection import connected
from tg_bot.modules.helper_funcs.decorators import kigcmd, kigmsg, kigcallback
from tg_bot.modules.helper_funcs.alternate import send_message, typing_action

from ..modules.helper_funcs.anonymous import user_admin as u_admin, AdminPerms, resolve_user as res_user, UserClass

BLACKLIST_GROUP = -3

@kigcmd(command=["blacklist", "blacklists", "blocklist", "blocklists"], pass_args=True, admin_ok=True)
@spamcheck
@user_admin
@typing_action
def blacklist(update, context):
    chat = update.effective_chat
    user = update.effective_user
    args = context.args

    conn = connected(context.bot, update, chat, user.id, need_admin=False)
    if conn:
        chat_id = conn
        chat_name = dispatcher.bot.getChat(conn).title
    else:
        if chat.type == "private":
            return
        chat_id = update.effective_chat.id
        chat_name = chat.title
    chat_name = html.escape(chat_name)
    filter_list = "<b>Blacklist settings for :{}</b>:\n".format(chat_name)
    getmode, getvalue = sql.get_blacklist_setting(chat.id)
    if getmode == 0:
        settypeblacklist = "Do nothing"
    elif getmode == 1:
        settypeblacklist = "Delete"
    elif getmode == 2:
        settypeblacklist = "Warn"
    elif getmode == 3:
        settypeblacklist = "Mute"
    elif getmode == 4:
        settypeblacklist = "Kick"
    elif getmode == 5:
        settypeblacklist = "Ban"
    elif getmode == 6:
        settypeblacklist = "Temporarily Ban for {}".format(getvalue)
    elif getmode == 7:
        settypeblacklist = "Temporarily Mute for {}".format(getvalue)
        
    filter_list += "ㅤ<b>Current blacklistmode:</b>\nㅤㅤ<b>{}</b>.\n".format(settypeblacklist)
    filter_list += "ㅤ<b>Current blacklisted words:</b>\n"
    all_blacklisted = sql.get_chat_blacklist(chat_id)
    actions = {
        0: "default",
        1: "delete",
        2: "warn",
        3: "mute",
        4: "kick",
        5: "ban",
    }
    if len(args) > 0 and args[0].lower() == "copy":
        for x in all_blacklisted:
            trigger = x[0]
            act = x[1]

            action = actions[act]
            filter_list += "ㅤ <code>{}</code>\nㅤㅤ  <b>Action:</b> {}\n".format(html.escape(trigger), action)
    else:
        for x in all_blacklisted:
            trigger = x[0]
            act = x[1]
            action = actions[act]
            filter_list += "ㅤㅤ- <code>{}</code>\nㅤㅤㅤ  <b>Action:</b> {}\n".format(html.escape(trigger), action)

    split_text = split_message(filter_list)
    for text in split_text:
        if len(all_blacklisted) == 0:
            send_message(
                update.effective_message,
                "No blacklisted words in <b>{}</b>!".format(chat_name),
                parse_mode=ParseMode.HTML,
            )
            return
        send_message(update.effective_message, text, parse_mode=ParseMode.HTML)

@kigcmd(command=["addblacklist", "addblocklist"], pass_args=True)
@spamcheck
@typing_action
@u_admin(UserClass.ADMIN, AdminPerms.CAN_CHANGE_INFO)
def add_blacklist(update, context):
    msg = update.effective_message
    chat = update.effective_chat
    u = update.effective_user
    words = msg.text.split(None, 1)
    user = res_user(u, msg.message_id, chat)

    conn = connected(context.bot, update, chat, user.id)
    if conn:
        chat_id = conn
        chat_name = dispatcher.bot.getChat(conn).title
    else:
        chat_id = update.effective_chat.id
        if chat.type == "private":
            return
        else:
            chat_name = chat.title
    chat_name = html.escape(chat_name)

    erroract = []

    if len(words) > 1:
        text = words[1]
        to_blacklist = list(
            {
                trigger.strip()
                for trigger in text.split("\n")
                if trigger.strip()
            }
        )
        for trigger in to_blacklist:
            if trigger.find(r" \{\w*\}") != -1:
                sql.add_to_blacklist(chat_id, trigger.lower(), 0)
                act = "default"
            else:
                trg = trigger.split(" {")[0]
                try:
                    act = trigger.split(" {")[1].replace("}", "")
                except IndexError:
                    act = "default"
                actions = {"delete", "warn", "mute", "kick", "ban"}
                if act in actions:
                    actionz = {
                        "delete": 1,
                        "warn": 2,
                        "mute": 3,
                        "kick": 4,
                        "ban": 5,
                    }
                    action = actionz[act]

                    sql.add_to_blacklist(chat_id, trg.lower(), action)
                
                else:
                    sql.add_to_blacklist(chat_id, trg.lower(), 0)
                    erroract.append(act)

        if len(to_blacklist) == 1:

            reply = "Added blacklist trigger: <code>{}</code> with <b>{}</b> action!"
            send_message(
                update.effective_message,
                reply.format(
                    html.escape(trg), act
                ),
                parse_mode=ParseMode.HTML,
            )

        else:
            reply = "Added blacklist <code>{}</code> in chat: <b>{}</b>!"
            if len(erroract) > 1:
                errstr = f"\nUnknown action(s): ({str(erroract)})\
                            \nThe possible actions are:\
                            \n{str(actions)}"
                reply += errstr
            send_message(
                update.effective_message,
                reply.format(
                    len(to_blacklist), chat_name
                ),
                parse_mode=ParseMode.HTML,
            )

    else:
        send_message(
            update.effective_message,
            "Tell me which words you would like to add in blacklist.",
        )

@kigcmd(command=["unblacklist", "unblocklist"], pass_args=True)
@spamcheck
@typing_action
@u_admin(UserClass.ADMIN, AdminPerms.CAN_CHANGE_INFO)
def unblacklist(update, context):
    msg = update.effective_message
    chat = update.effective_chat
    u = update.effective_user
    words = msg.text.split(None, 1)
    user = res_user(u, msg.message_id, chat)

    conn = connected(context.bot, update, chat, user.id)
    if conn:
        chat_id = conn
        chat_name = dispatcher.bot.getChat(conn).title
    else:
        chat_id = update.effective_chat.id
        if chat.type == "private":
            return
        else:
            chat_name = chat.title
    chat_name = html.escape(chat_name)

    if len(words) > 1:
        text = words[1]
        to_unblacklist = list(
            {
                trigger.strip()
                for trigger in text.split("\n")
                if trigger.strip()
            }
        )

        successful = 0
        for trigger in to_unblacklist:
            success = sql.rm_from_blacklist(chat_id, trigger.lower())
            if success:
                successful += 1

        if len(to_unblacklist) == 1:
            if successful:
                send_message(
                    update.effective_message,
                    "Removed <code>{}</code> from blacklist in <b>{}</b>!".format(
                        html.escape(to_unblacklist[0]), chat_name
                    ),
                    parse_mode=ParseMode.HTML,
                )
            else:
                send_message(
                    update.effective_message, "This is not a blacklist trigger!"
                )

        elif successful == len(to_unblacklist):
            send_message(
                update.effective_message,
                "Removed <code>{}</code> from blacklist in <b>{}</b>!".format(
                    successful, chat_name
                ),
                parse_mode=ParseMode.HTML,
            )

        elif not successful:
            send_message(
                update.effective_message,
                "None of these triggers exist so it can't be removed.".format(
                    successful, len(to_unblacklist) - successful
                ),
                parse_mode=ParseMode.HTML,
            )

        else:
            send_message(
                update.effective_message,
                "Removed <code>{}</code> from blacklist. {} did not exist, "
                "so were not removed.".format(
                    successful, len(to_unblacklist) - successful
                ),
                parse_mode=ParseMode.HTML,
            )
    else:
        send_message(
            update.effective_message,
            "Tell me which words you would like to remove from blacklist!",
        )

@kigcmd(command=["blacklistmode", "blocklistmode"], pass_args=True)
@spamcheck
@typing_action
@loggable
@u_admin(UserClass.ADMIN, AdminPerms.CAN_CHANGE_INFO)
def blacklist_mode(update, context):  # sourcery no-metrics
    chat = update.effective_chat
    u = update.effective_user
    msg = update.effective_message
    args = context.args
    
    user = res_user(u, msg.message_id, chat)

    conn = connected(context.bot, update, chat, user.id, need_admin=True)
    if conn:
        chat = dispatcher.bot.getChat(conn)
        chat_id = conn
        chat_name = dispatcher.bot.getChat(conn).title
    else:
        if update.effective_message.chat.type == "private":
            send_message(
                update.effective_message,
                "This command can be only used in group not in PM",
            )
            return ""
        chat = update.effective_chat
        chat_id = update.effective_chat.id
        chat_name = update.effective_message.chat.title
    chat_name = html.escape(chat_name)

    if args:
        if args[0].lower() in ["off", "nothing", "no"]:
            settypeblacklist = "do nothing"
            sql.set_blacklist_strength(chat_id, 0, "0")
        elif args[0].lower() in ["del", "delete"]:
            settypeblacklist = "will delete blacklisted message"
            sql.set_blacklist_strength(chat_id, 1, "0")
        elif args[0].lower() == "warn":
            settypeblacklist = "warn the sender"
            sql.set_blacklist_strength(chat_id, 2, "0")
        elif args[0].lower() == "mute":
            settypeblacklist = "mute the sender"
            sql.set_blacklist_strength(chat_id, 3, "0")
        elif args[0].lower() == "kick":
            settypeblacklist = "kick the sender"
            sql.set_blacklist_strength(chat_id, 4, "0")
        elif args[0].lower() == "ban":
            settypeblacklist = "ban the sender"
            sql.set_blacklist_strength(chat_id, 5, "0")
        elif args[0].lower() == "tban":
            if len(args) == 1:
                teks = """It looks like you tried to set time value for blacklist but you didn't specified time; Try, `/blacklistmode tban <timevalue>`.

Examples of time value: 4m = 4 minutes, 3h = 3 hours, 6d = 6 days, 5w = 5 weeks."""
                send_message(update.effective_message, teks, parse_mode="markdown")
                return ""
            restime = extract_time(msg, args[1])
            if not restime:
                teks = """Invalid time value!
Example of time value: 4m = 4 minutes, 3h = 3 hours, 6d = 6 days, 5w = 5 weeks."""
                send_message(update.effective_message, teks, parse_mode="markdown")
                return ""
            settypeblacklist = "temporarily ban for {}".format(args[1])
            sql.set_blacklist_strength(chat_id, 6, str(args[1]))
        elif args[0].lower() == "tmute":
            if len(args) == 1:
                teks = """It looks like you tried to set time value for blacklist but you didn't specified  time; try, `/blacklistmode tmute <timevalue>`.

Examples of time value: 4m = 4 minutes, 3h = 3 hours, 6d = 6 days, 5w = 5 weeks."""
                send_message(update.effective_message, teks, parse_mode="markdown")
                return ""
            restime = extract_time(msg, args[1])
            if not restime:
                teks = """Invalid time value!
Examples of time value: 4m = 4 minutes, 3h = 3 hours, 6d = 6 days, 5w = 5 weeks."""
                send_message(update.effective_message, teks, parse_mode="markdown")
                return ""
            settypeblacklist = "temporarily mute for {}".format(args[1])
            sql.set_blacklist_strength(chat_id, 7, str(args[1]))
        else:
            send_message(
                update.effective_message,
                "I only understand: off/del/warn/ban/kick/mute/tban/tmute!",
            )
            return ""
        if conn:
            text = "Changed blacklist mode: `{}` in *{}*!".format(
                settypeblacklist, chat_name
            )
        else:
            text = "Changed blacklist mode: `{}`!".format(settypeblacklist)
        send_message(update.effective_message, text, parse_mode="markdown")
        return (
            "<b>{}:</b>\n"
            "<b>Admin:</b> {}\n"
            "Changed the blacklist mode. will {}.".format(
                html.escape(chat.title),
                mention_html(user.id, user.first_name),
                settypeblacklist,
            )
        )
    else:
        getmode, getvalue = sql.get_blacklist_setting(chat.id)
        if getmode == 0:
            settypeblacklist = "do nothing"
        elif getmode == 1:
            settypeblacklist = "delete"
        elif getmode == 2:
            settypeblacklist = "warn"
        elif getmode == 3:
            settypeblacklist = "mute"
        elif getmode == 4:
            settypeblacklist = "kick"
        elif getmode == 5:
            settypeblacklist = "ban"
        elif getmode == 6:
            settypeblacklist = "temporarily ban for {}".format(getvalue)
        elif getmode == 7:
            settypeblacklist = "temporarily mute for {}".format(getvalue)
        if conn:
            text = "Current blacklistmode: *{}* in *{}*.".format(
                settypeblacklist, chat_name
            )
        else:
            text = "Current blacklistmode: *{}*.".format(settypeblacklist)
        send_message(update.effective_message, text, parse_mode=ParseMode.MARKDOWN)
    return ""


def findall(p, s):
    i = s.find(p)
    while i != -1:
        yield i
        i = s.find(p, i + 1)



@kigmsg(((Filters.text | Filters.command | Filters.sticker | Filters.photo) & Filters.chat_type.groups), group=BLACKLIST_GROUP)
@user_not_admin
def del_blacklist(update, context):  # sourcery no-metrics
    chat = update.effective_chat
    message = update.effective_message
    user = update.effective_user
    bot = context.bot
    to_match = extract_text(message)
    if not to_match:
        return
    if is_approved(chat.id, user.id):
        return
    getmode, value = sql.get_blacklist_setting(chat.id)

    chat_filters = sql.get_chat_blacklist(chat.id)

    for tuptrigger in chat_filters:
        trigger = str(tuptrigger[0])
        getmode = (int(tuptrigger[1]) if int(tuptrigger[1]) > 0 else getmode)
        pattern = r"( |^|[^\w])" + re.escape(trigger) + r"( |$|[^\w])"
        if re.search(pattern, to_match, flags=re.IGNORECASE):
            try:
                if getmode == 0:
                    return
                elif getmode == 1:
                    message.delete()
                elif getmode == 2:
                    message.delete()
                    warn(
                        update.effective_user,
                        chat,
                        ("Using blacklisted trigger: {}".format(trigger)),
                        message,
                        update.effective_user,
                    )
                    return
                elif getmode == 3:
                    message.delete()
                    bot.restrict_chat_member(
                        chat.id,
                        update.effective_user.id,
                        permissions=ChatPermissions(can_send_messages=False),
                    )
                    bot.sendMessage(
                        chat.id,
                        f"Muted {user.first_name} for using Blacklisted word: {trigger}!",
                    )
                    return
                elif getmode == 4:
                    message.delete()
                    res = chat.unban_member(update.effective_user.id)
                    if res:
                        bot.sendMessage(
                            chat.id,
                            f"Kicked {user.first_name} for using Blacklisted word: {trigger}!",
                        )
                    return
                elif getmode == 5:
                    message.delete()
                    chat.ban_member(user.id)
                    bot.sendMessage(
                        chat.id,
                        f"Banned {user.first_name} for using Blacklisted word: {trigger}",
                    )
                    return
                elif getmode == 6:
                    message.delete()
                    bantime = extract_time(message, value)
                    chat.ban_member(user.id, until_date=bantime)
                    bot.sendMessage(
                        chat.id,
                        f"Banned {user.first_name} until '{value}' for using Blacklisted word: {trigger}!",
                    )
                    return
                elif getmode == 7:
                    message.delete()
                    mutetime = extract_time(message, value)
                    bot.restrict_chat_member(
                        chat.id,
                        user.id,
                        until_date=mutetime,
                        permissions=ChatPermissions(can_send_messages=False),
                    )
                    bot.sendMessage(
                        chat.id,
                        f"Muted {user.first_name} until '{value}' for using Blacklisted word: {trigger}!",
                    )
                    return
            except BadRequest as excp:
                if excp.message != "Message to delete not found":
                    log.exception("Error while deleting blacklist message.")
            break

from telegram import ParseMode, InlineKeyboardMarkup, InlineKeyboardButton

@kigcmd(command=["removeallblacklists", "removeallblocklists"], filters=Filters.chat_type.groups)
@spamcheck
def rmall_filters(update, context):
    chat = update.effective_chat
    user = update.effective_user
    member = chat.get_member(user.id)
    if member.status != "creator" and user.id not in SUDO_USERS:
        update.effective_message.reply_text(
            "Only the chat owner can clear all blacklists at once."
        )
    else:
        buttons = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        text="Remove all Blacklists", callback_data="blacklists_rmall"
                    )
                ],
                [InlineKeyboardButton(text="Cancel", callback_data="blacklists_cancel")],
            ]
        )
        update.effective_message.reply_text(
            f"Are you sure you would like to stop ALL blacklists in {chat.title}? This action cannot be undone.",
            reply_markup=buttons,
            parse_mode=ParseMode.MARKDOWN,
        )

@kigcallback(pattern=r"blacklists_.*")
@loggable
def rmall_callback(update, context) -> str:
    query = update.callback_query
    chat = update.effective_chat
    msg = update.effective_message
    member = chat.get_member(query.from_user.id)
    user = query.from_user
    if query.data == "blacklists_rmall":
        if member.status == "creator" or query.from_user.id in SUDO_USERS:
            allfilters = sql.get_chat_blacklist(chat.id)
            if not allfilters:
                msg.edit_text("No blacklists in this chat, nothing to stop!")
                return ""

            count = 0
            filterlist = []
            for x in allfilters:
                count += 1
                filterlist.append(x)
            print(filterlist)
            for i in filterlist:
                sql.rm_from_blacklist(chat.id, i[0])

            msg.edit_text(f"Cleaned {count} bl in {chat.title}")

            log_message = (
                f"<b>{html.escape(chat.title)}:</b>\n"
                f"#CLEAREDALLBLACKLISTS\n"
                f"<b>Admin:</b> {mention_html(user.id, html.escape(user.first_name))}"
            )
            return log_message

        if member.status == "administrator":
            query.answer("Only owner of the chat can do this.")
            return ""

        if member.status == "member":
            query.answer("You need to be admin to do this.")
            return ""
    elif query.data == "blacklists_cancel":
        if member.status == "creator" or query.from_user.id in SUDO_USERS:
            msg.edit_text("Clearing of all filters has been cancelled.")
            return ""
        if member.status == "administrator":
            query.answer("Only owner of the chat can do this.")
            return ""
        if member.status == "member":
            query.answer("You need to be admin to do this.")
            return ""


def __import_data__(chat_id, data):
    # set chat blacklist
    blacklist = data.get("blacklist", {})
    for trigger in blacklist:
        sql.add_to_blacklist(chat_id, trigger)


def __migrate__(old_chat_id, new_chat_id):
    sql.migrate_chat(old_chat_id, new_chat_id)


def __chat_settings__(chat_id, user_id):
    blacklisted = sql.num_blacklist_chat_filters(chat_id)
    return "There are {} blacklisted words.".format(blacklisted)


def __stats__():
    return "• {} blacklist triggers, across {} chats.".format(
        sql.num_blacklist_filters(), sql.num_blacklist_filter_chats()
    )


__mod_name__ = "Blacklists"

from tg_bot.modules.language import gs

def get_help(chat):
    return gs(chat, "blacklist_help")
