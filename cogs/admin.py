import subprocess

import discord
from discord.ext import commands

import cogs.economy as economy


class Admin(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.economy_engine: economy.Economy = self.bot.get_cog('Economy')

    async def cog_check(self, ctx):
        permissions = ctx.author.guild_permissions
        return permissions.administrator

    @commands.command(name='set-coins', usage="{}set-coins <member> <amount>")
    async def set_coins(self, ctx, member: discord.Member, amount: int):
        self.economy_engine.set_balance(member, amount)

        await self.bot.send_success_embed(ctx, 'set_coins_success', member.display_name, amount)

    @commands.command(name='add-coins', usage="{}add-coins <member> <amount>")
    async def add_coins(self, ctx, member: discord.Member, amount: int):
        new_amount = self.economy_engine.add_to_balance(member, amount)

        await self.bot.send_success_embed(ctx, 'add_coins_success', amount, member.display_name, new_amount)

    @commands.command(name='remove-coins', usage="{}remove-coins <member> <amount>")
    async def remove_coins(self, ctx, member: discord.Member, amount: int):
        new_amount = self.economy_engine.add_to_balance(member, -amount)

        await self.bot.send_success_embed(ctx, 'remove_coins_success', amount, member.display_name, new_amount)

    @commands.command(name='set-company-coins', usage="{}set-company-coins <company> <amount>")
    async def set_company_coins(self, ctx, company_name: str, amount: int):
        new_amount = self.economy_engine.set_company_balance(company_name, amount)

        if new_amount is None:
            await self.bot.send_error_embed(ctx, 'company_not_found')
        else:
            await self.bot.send_success_embed(ctx, 'set_company_coins_success', company_name, new_amount)

    @commands.command(name="user-coins", usage="{}user-coins <member>")
    async def user_coins(self, ctx, member: discord.Member):
        amount, donated = self.economy_engine.get_balance(member)

        if amount is None:
            await self.bot.send_error_embed(ctx, 'member_not_in_database', member.display_name)
        else:
            await self.bot.send_success_embed(ctx, 'show_member_coins', member.display_name, amount)

    @commands.command(name="company-coins", usage="{}company-coins <company>")
    async def company_coins(self, ctx, company_name: str):
        amount = self.economy_engine.get_company_balance(company_name)

        if amount is None:
            await self.bot.send_error_embed(ctx, 'company_not_found')
        else:
            await self.bot.send_success_embed(ctx, 'show_company_coins', company_name, amount)

    @commands.command(usage="{}blacklist <member>")
    async def blacklist(self, ctx, member: discord.Member):
        self.economy_engine.blacklist(member)

        await self.bot.send_success_embed(ctx, 'blacklist_success', member.display_name)

    @commands.command(name='blacklist-remove', usage="{}blacklist-remove <member>")
    async def blacklist_remove(self, ctx, member: discord.Member):
        self.economy_engine.remove_from_blacklist(member)

        await self.bot.send_success_embed(ctx, 'blacklist_remove_success', member.display_name)

    @commands.command(name='blacklist-role', usage="{}blacklist-role <role>")
    async def blacklist_role(self, ctx, role: discord.Role):
        self.economy_engine.blacklist_role(role)

        await self.bot.send_success_embed(ctx, 'blacklist_role_success', role.name)

    @commands.command(name='toggle-pay', usage='{}toggle-pay')
    async def toggle_pay(self, ctx):
        pay_enabled = self.bot.cfg['pay_enabled']
        pay_enabled = not pay_enabled
        self.bot.cfg['pay_enabled'] = pay_enabled
        self.bot.cfg.write()

        await self.bot.send_success_embed(ctx, 'pay_toggle_success', pay_enabled)

    @commands.command(name='toggle-deposit', usage='{}toggle-deposit')
    async def toggle_deposit(self, ctx):
        deposit_enabled = self.bot.cfg['deposit_enabled']
        deposit_enabled = not deposit_enabled
        self.bot.cfg['deposit_enabled'] = deposit_enabled
        self.bot.cfg.write()

        await self.bot.send_success_embed(ctx, 'deposit_toggle_success', deposit_enabled)

    @commands.command(name='give-service', usage='{}give-service <member> <service name>')
    async def give_user_service(self, ctx, member: discord.Member, *, service_name: str):
        await self.bot.get_cog('User').give_user_service(ctx, ctx.guild, member, service_name, True)

    @commands.command(name='give-company-service', usage='{}give-company-service <guild admin> <service name>')
    async def give_company_service(self, ctx, member: discord.Member, *, service_name: str):
        await self.bot.get_cog('User').give_company_service(ctx, ctx.guild, member, service_name, True)

    @commands.command(name='coins-reload', usage="{}coins-reload")
    async def coins_reload(self, ctx):
        await self.bot.send_success_embed(ctx, 'reloading')

        subprocess.call(['service', self.bot.cfg['service_name'], 'restart'])
