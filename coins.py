import logging
import logging.handlers
from configobj import ConfigObj

import discord
from discord.ext import commands
from validate import Validator

from cogs import economy, user, admin, companies
from cogs.user import User
from database import Database

logging.basicConfig(level=logging.INFO)
fh = logging.handlers.RotatingFileHandler('logs/error.log', maxBytes=1000000, backupCount=4)
fh.setLevel(logging.INFO)
fh.setFormatter(logging.Formatter(fmt='%(asctime)s %(levelname)s : %(name)s : %(message)s', datefmt='%m-%d %H:%M:%S'))
logging.getLogger('').addHandler(fh)


class Config:
    def __init__(self):
        self.cfgspec = ['coins_gain = integer', 'role = integer', 'user_command_channel = integer',
                        'service_category = integer', 'guild_service_category = integer',
                        'governatore_role = integer', 'console_role = integer',
                        'pay_enabled = boolean', 'deposit_enabled = boolean',
                        '[CoinsByChat]', 'coins_for_message = float', 'min_chars = integer',
                        'whitelisted_channels = sorted_id_list',
                        '[SpecialRoles]', '__many__ = integer',
                        '[Services]', '[[__many__]]', 'cost = integer', 'notify_to = integer', 'role_to_add = integer',
                        '[CompanyServices]', '[[__many__]]', 'cost = integer', 'notify_to = integer',
                        'role_to_add = integer']
        self.checks = {
            'sorted_id_list': self.sorted_id_list
        }

    def load(self):
        cfg = ConfigObj('config.ini', configspec=self.cfgspec, encoding='utf8')
        cfg.validate(Validator(self.checks))
        return cfg

    def sorted_id_list(self, value: str):
        ids = list()
        for string in value:
            if len(string) != 0:
                ids.append(int(string.strip()))
        return sorted(ids)


class CoinsClient(commands.Bot):
    def __init__(self, **options):
        self.cfg = Config().load()

        self.db = None
        self.company_staff_roles = {}
        super().__init__(self.cfg['Prefix'], **options)

        self.add_check(self.globally_block_dms)

    async def on_ready(self):
        self.db = Database(self)
        self.load_cogs()
        self.fetch_roles()

        await self.change_presence(activity=discord.Activity(type=discord.ActivityType.listening,
                                                             name=f"{self.command_prefix}coins"))

        logging.info("Coins loaded in {0} servers".format(len(self.guilds)))

    async def on_command_error(self, ctx, exception):
        if isinstance(exception, (commands.errors.MissingRequiredArgument, commands.errors.TooManyArguments)):
            await self.send_error_embed(ctx, 'incorrect_command_usage', ctx.command.usage.format(self.command_prefix))
        elif isinstance(exception, commands.errors.BadArgument):
            await self.send_error_embed(ctx, 'bad_command_arguments')
        elif isinstance(exception, commands.errors.CheckFailure):
            if ctx.cog.qualified_name == 'Admin':
                await self.send_error_embed(ctx, 'no_permissions')
        elif isinstance(exception, User.Blacklisted):
            await self.send_error_embed(ctx, 'blacklisted')
        elif isinstance(exception, commands.errors.CommandNotFound):
            pass
        else:
            await super().on_command_error(ctx, exception)

    async def globally_block_dms(self, ctx):
        return ctx.guild is not None

    def load_cogs(self):
        self.add_cog(companies.Companies(self))
        self.add_cog(economy.Economy(self))
        self.add_cog(user.User(self))
        self.add_cog(admin.Admin(self))

    def fetch_roles(self):
        self.company_staff_roles['governatore'] = self.guilds[0].get_role(self.cfg['governatore_role'])
        self.company_staff_roles['console'] = self.guilds[0].get_role(self.cfg['console_role'])
        if self.company_staff_roles['governatore'] is None or self.company_staff_roles['console'] is None:
            logging.error("Governatore or Console role not correctly set")

    def get_message(self, message: str, *args):
        return (self.cfg['Messages'][message] % args).replace('\\n', '\n')

    async def send_success_embed(self, ctx, message: str, *args):
        embed = discord.Embed(
            color=discord.Colour.green(),
            description=self.get_message(message, *args))
        await ctx.send(embed=embed)

    async def send_error_embed(self, ctx, message: str, *args):
        embed = discord.Embed(
            color=discord.Colour.red(),
            description=self.get_message(message, *args))
        await ctx.send(embed=embed)


intents = discord.Intents.default()
intents.members = True

bot = CoinsClient(case_insensitive=True, help_command=None, intents=intents)
bot.run(bot.cfg['Token'])
