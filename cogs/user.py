import bisect

import discord
from discord.ext import commands
from discord.ext.commands import BadArgument

import cogs.economy as economy
from cogs import companies


def binary_search(a, x):
    i = bisect.bisect_left(a, x)
    if len(a) > i and a[i] != x:
        return -1


class User(commands.Cog):
    class MemberMentioned(commands.Converter):
        async def convert(self, ctx, argument):
            if argument.startswith('<@!') and argument.endswith('>') and len(ctx.message.mentions) == 1:
                return ctx.message.mentions[0]
            else:
                raise BadArgument('Member "{}" not found'.format(argument))

    class Blacklisted(commands.errors.UserInputError):
        pass

    def __init__(self, bot):
        self.bot = bot
        self.economy_engine: economy.Economy = self.bot.get_cog('Economy')
        self.company_manager: companies.Companies = self.bot.get_cog('Companies')

    async def cog_check(self, ctx: commands.Context) -> bool:
        is_cmd_channel = True
        cmd_channel = self.bot.cfg['user_command_channel']
        if cmd_channel != '' and not ctx.author.guild_permissions.administrator:
            is_cmd_channel = cmd_channel == ctx.channel.id

        if is_cmd_channel and self.economy_engine.is_blacklisted(ctx.author):
            raise self.Blacklisted()
        return is_cmd_channel

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot:
            return
        if message.channel.type != discord.ChannelType.text:
            return
        whitelisted_channels = self.bot.cfg['CoinsByChat']['whitelisted_channels']
        if len(whitelisted_channels) != 0:
            if binary_search(whitelisted_channels, message.channel.id) == -1:
                return

        if len(message.content) >= self.bot.cfg['CoinsByChat']['min_chars']:
            self.economy_engine.add_to_balance(message.author, self.bot.cfg['CoinsByChat']['coins_for_message'])

    @commands.command(name="saldo", usage="{}saldo", description="Mostra il tuo saldo")
    async def balance(self, ctx):
        balance, donated = self.economy_engine.get_balance(ctx.author)
        user_profile_pic_url = ctx.author.avatar_url_as(size=64)
        description = ""
        if donated > 0:
            description = self.bot.get_message('balance_embed_description_with_donations', balance, donated)
        else:
            description = self.bot.get_message('balance_embed_description', balance)
        balance_embed = discord.Embed(color=discord.colour.Colour.dark_gold(),
                                      title=f'**{ctx.author.display_name}**',
                                      description=description)
        balance_embed.set_thumbnail(url=user_profile_pic_url)

        await ctx.send(embed=balance_embed)

    @commands.command(name="saldo-compagnia", usage="{}saldo-compagnia",
                      description="Mostra il saldo della tua Compagnia")
    async def company_balance(self, ctx):
        company_name = self.company_manager.get_company_for(ctx.author)
        if company_name is None:
            await self.bot.send_error_embed(ctx, 'not_in_company')
        else:
            balance = self.economy_engine.get_company_balance(company_name)
            balance_embed = discord.Embed(color=discord.Colour.dark_gold(),
                                          title=f'**{company_name}**',
                                          description=self.bot.get_message('company_balance_embed_description',
                                                                           balance))
            await ctx.send(embed=balance_embed)

    @commands.command(name="paga", usage="{}paga <utente> <quantità>", description="Paga un altro utente")
    async def pay(self, ctx, member: MemberMentioned, amount: int):
        if not self.bot.cfg['pay_enabled'] and not ctx.author.guild_permissions.administrator:
            await self.bot.send_error_embed(ctx, 'pay_not_enabled')
            return
        if amount <= 0:
            await self.bot.send_error_embed(ctx, 'pay_incorrect_amount')
        else:
            new_balance = self.economy_engine.payment(ctx.author, member, amount)
            if new_balance == -1:
                await self.bot.send_error_embed(ctx, 'not_enough_coins')
            else:
                await self.bot.send_success_embed(ctx, 'pay_success', member.display_name, amount, new_balance)

    @commands.command(name='deposita', usage="{}deposita <quantità>",
                      description="Deposita dei coins nella banca della tua Compagnia")
    async def company_deposit(self, ctx, amount: int):
        if not self.bot.cfg['deposit_enabled'] and not ctx.author.guild_permissions.administrator:
            await self.bot.send_error_embed(ctx, 'deposit_not_enabled')
            return
        if amount <= 0:
            await self.bot.send_error_embed(ctx, 'pay_incorrect_amount')
        else:
            company_name = self.company_manager.get_company_for(ctx.author)
            if company_name is None:
                await self.bot.send_error_embed(ctx, 'not_in_company')
            else:
                new_balance = self.economy_engine.company_deposit(ctx.author, amount)
                if new_balance == -1:
                    await self.bot.send_error_embed(ctx, 'not_enough_coins')
                else:
                    await self.bot.send_success_embed(ctx, 'deposit_success', amount, new_balance)

    @commands.command(name='top-donatori', usage="{}top-donatori",
                      description="Visualizza la classifica dei top 10 donatori della tua Compagnia")
    async def company_top_donors(self, ctx):
        company_name = self.company_manager.get_company_for(ctx.author)
        if company_name is None:
            await self.bot.send_error_embed(ctx, 'not_in_company')
            return

        top_donors = self.economy_engine.company_top_donors(company_name)
        top_donors_embed = discord.Embed(color=discord.Colour.dark_gold(),
                                         title=self.bot.get_message('company_top_donors_embed_title'))
        description = ""
        for member_id, donated in top_donors:
            member_name = ctx.guild.get_member(member_id).display_name
            description += f"{self.bot.get_message('company_top_donors_embed_line', member_name, donated)}\n"
        top_donors_embed.description = description

        await ctx.send(embed=top_donors_embed)

    @commands.command(usage="{}top", description="Mostra la classifica dei 10 utenti più ricchi")
    async def top(self, ctx):
        top_embed = self.economy_engine.top(ctx.guild)
        await ctx.send(embed=top_embed)

    @commands.command(name='top-compagnie', usage="{}top-compagnie",
                      description="Mostra la classifica delle 10 Compagnie più ricche")
    async def companies_top(self, ctx):
        companies_top_embed = self.economy_engine.companies_top()
        await ctx.send(embed=companies_top_embed)

    @commands.command(name='servizi', usage="{}servizi", description="Mostra la lista dei servizi acquistabili")
    async def services(self, ctx):
        services_embed = discord.Embed(color=discord.Colour.dark_gold(),
                                       title=self.bot.get_message('services_embed_title'))
        services = self.bot.cfg['Services']
        content = ""

        for service_name in services:
            content += '%s\n' % self.bot.get_message('services_embed_line', service_name,
                                                     services[service_name]['cost'],
                                                     services[service_name]['description'])
        services_embed.description = content[:len(content)]

        await ctx.send(embed=services_embed)

    @commands.command(name='servizi-compagnie', usage="{}servizi-compagnie",
                      description="Mostra la lista dei servizi acquistabili dalle Compagnie")
    async def companies_services(self, ctx):
        company_services_embed = discord.Embed(color=discord.Colour.dark_gold(),
                                               title=self.bot.get_message('company_services_embed_title'))
        company_services = self.bot.cfg['CompanyServices']
        content = ""

        for service_name in company_services:
            content += '%s\n' % self.bot.get_message('company_services_embed_line', service_name,
                                                     company_services[service_name]['cost'],
                                                     company_services[service_name]['description'])
        company_services_embed.description = content

        await ctx.send(embed=company_services_embed)

    @commands.command(name='servizio', usage="{}servizio <servizio>", description="Compra il servizio")
    async def service(self, ctx, *, service_name):
        await self.give_user_service(ctx, ctx.guild, ctx.author, service_name, False)

    @commands.command(name='servizio-compagnia', usage="{}servizio-compagnia <servizio>",
                      description="Compra il servizio per la tua Compagnia")
    async def company_service(self, ctx, *, service_name):
        await self.give_company_service(ctx, ctx.guild, ctx.author, service_name, False)

    @commands.command(name='coins', usage="{}coins", description="Mostra questo messaggio di aiuto")
    async def coins_help(self, ctx):
        help_embed = discord.Embed(color=discord.Colour.blue(), title='__**Comandi Coins**__')

        prefix = self.bot.command_prefix
        user_cmd = ''
        for command in self.get_commands():
            user_cmd += '`%s` **-** *%s*\n' % (command.usage.format(prefix), command.description)
        help_embed.add_field(name='Ecco la lista dei comandi:', value=user_cmd)

        if ctx.author.guild_permissions.administrator:
            admin_cmd = ''
            for command in self.bot.get_cog('Admin').get_commands():
                admin_cmd += '`%s` **-** *%s*\n' % (command.usage.format(prefix), command.description)
            help_embed.add_field(name='Comandi Amministratore:', value=admin_cmd)

        await ctx.send(embed=help_embed)

    async def give_user_service(self, ctx: commands.Context, server: discord.Guild, member: discord.Member, service_name: str, force: bool):
        services = self.bot.cfg['Services']
        found = False

        for service in services:
            if service.lower() == service_name.lower():
                found = True
                result = await self.economy_engine.buy_service(server, member, service, force)
                if result != -1:
                    await self.bot.send_success_embed(ctx, 'service_buy_success', service, result)
                else:
                    await self.bot.send_error_embed(ctx, 'not_enough_coins')

        if not found:
            await self.bot.send_error_embed(ctx, 'service_not_found', service_name)

    async def give_company_service(self, ctx: commands.Context, server: discord.Guild, member: discord.Member, service_name: str, force: bool):
        company_name = self.company_manager.get_company_for(member)
        if company_name is None:
            await self.bot.send_error_embed(ctx, 'not_in_company')
            return

        if self.company_manager.is_staff(member):
            company_services = self.bot.cfg['CompanyServices']
            found = False

            for service in company_services:
                if service.lower() == service_name.lower():
                    found = True
                    result = await self.economy_engine.buy_company_service(server, member, company_name, service, force)
                    if result != -1:
                        await self.bot.send_success_embed(ctx, 'service_buy_success', service, result)
                    else:
                        await self.bot.send_error_embed(ctx, 'not_enough_coins')

            if not found:
                await self.bot.send_error_embed(ctx, 'service_not_found', service_name)
        else:
            await self.bot.send_error_embed(ctx, 'not_company_admin')
