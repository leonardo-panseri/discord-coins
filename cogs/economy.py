import logging
import timeit

import discord
from discord.ext import commands, tasks
from sqlalchemy import or_
from sqlalchemy.orm import Session

from database import Database


class Economy(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.user_model: Database.User.__class__ = self.bot.db.User
        self.company_model: Database.Company.__class__ = self.bot.db.Company
        self.special_roles: dict = self.bot.cfg['SpecialRoles']

        self.coins_gain = self.bot.cfg['coins_gain']
        self.role = self.bot.cfg['role']
        self.coins_tick.start()

    def create_session(self) -> Session:
        return self.bot.db.Session()

    def is_blacklisted(self, member: discord.Member):
        session = self.create_session()
        query = session.query(self.user_model).filter_by(member_id=member.id)

        session.close()

        if query.count() == 1:
            return query[0].blacklisted
        else:
            return False

    @tasks.loop(minutes=1.0)
    async def coins_tick(self):
        start = timeit.default_timer()

        session = self.create_session()
        for guild in self.bot.guilds:
            if guild.unavailable:
                pass
            for channel in guild.voice_channels:
                if len(channel.members) < 2:
                    continue
                unmuted = list()
                for member in channel.members:
                    v = member.voice
                    if (not v.afk and discord.utils.get(member.roles, id=self.role) is not None
                            and not (v.deaf or v.mute or v.self_deaf or v.self_mute)):
                        unmuted.append(member)

                if len(unmuted) > 1:
                    for member in unmuted:
                        query = session.query(self.user_model).filter_by(member_id=member.id)

                        new_amount = self.coins_gain
                        if query.count() == 1:
                            if not query[0].blacklisted:
                                new_amount += query[0].balance
                                query[0].balance = new_amount
                        else:
                            user = self.user_model(member_id=member.id, balance=new_amount)
                            session.add(user)

        session.commit()
        stop = timeit.default_timer()
        tot = stop - start
        if tot > 10:
            logging.warning('coins_tick took longer than 10s')

    @commands.Cog.listener()
    async def on_member_update(self, before: discord.Member, after: discord.Member):
        if len(before.roles) < len(after.roles):
            new_role = next(role for role in after.roles if role not in before.roles)
            if str(new_role.id) in self.special_roles:
                self.add_to_balance(after, self.special_roles[str(new_role.id)])
        return

    def set_balance(self, member: discord.Member, amount: int):
        session = self.create_session()
        user = self.user_model(member_id=member.id, balance=amount)
        session.merge(user)
        session.commit()
        session.close()

    def set_company_balance(self, company_name: str, amount: int):
        session = self.create_session()
        query = session.query(self.company_model).filter_by(name=company_name)

        if query.count() == 1:
            query[0].balance = amount
        else:
            return None

        session.commit()
        session.close()
        return amount

    def add_to_balance(self, member: discord.Member, amount: int):
        session = self.create_session()
        query = session.query(self.user_model).filter_by(member_id=member.id)

        new_amount = amount
        if query.count() == 1:
            new_amount += query[0].balance
            query[0].balance = new_amount
        else:
            user = self.user_model(member_id=member.id, balance=new_amount)
            session.add(user)

        session.commit()
        session.close()
        return new_amount

    def get_balance(self, member: discord.Member):
        session = self.create_session()
        query = session.query(self.user_model).filter_by(member_id=member.id)

        session.close()

        if query.count() == 1:
            return query[0].balance, query[0].company_donations
        else:
            return 0, 0

    def get_company_balance(self, company_name: str):
        session = self.create_session()
        query = session.query(self.company_model).filter_by(name=company_name)

        session.close()

        if query.count() == 1:
            return query[0].balance
        else:
            return 0

    def blacklist(self, member: discord.Member):
        session = self.create_session()
        user = self.user_model(member_id=member.id, blacklisted=True)
        session.merge(user)
        session.commit()
        session.close()

    def remove_from_blacklist(self, member: discord.Member):
        session = self.create_session()
        user = self.user_model(member_id=member.id, blacklisted=False)
        session.merge(user)
        session.commit()
        session.close()

    def blacklist_role(self, role: discord.Role):
        session = self.create_session()
        for member in role.members:
            user = self.user_model(member_id=member.id, blacklisted=True)
            session.merge(user)
        session.commit()
        session.close()

    def payment(self, sender: discord.Member, receiver: discord.Member, amount: int):
        session = self.create_session()
        query = session.query(self.user_model) \
            .filter(or_(self.user_model.member_id == sender.id, self.user_model.member_id == receiver.id))

        if query.count() == 2:
            if query[0].member_id == sender.id:
                user_sender = query[0]
                user_receiver = query[1]
            else:
                user_receiver = query[0]
                user_sender = query[1]
        elif query.count() == 1:
            if query[0].member_id == sender.id:
                user_sender = query[0]
                user_receiver = self.user_model(member_id=receiver.id, balance=0)
                session.add(user_receiver)
            else:
                return -1
        else:
            return -1

        if user_sender.balance < amount:
            return -1

        user_sender.balance -= amount
        user_receiver.balance += amount

        sender_final_balance = user_sender.balance

        session.commit()
        session.close()
        return sender_final_balance

    def company_deposit(self, sender: discord.Member, amount: int):
        session = self.create_session()
        query = session.query(self.user_model).filter_by(member_id=sender.id)

        if query.count() == 1:
            user_sender = query[0]
            if user_sender.balance >= amount:
                user_sender.company.balance += amount

                user_sender.balance -= amount
                user_sender.company_donations += amount
                session.commit()
                return user_sender.balance

        session.close()
        return -1

    def top(self, server: discord.Guild):
        session = self.create_session()
        query = session.query(self.user_model).order_by(self.user_model.balance.desc()).limit(10)

        session.close()

        top_embed = discord.Embed(color=discord.colour.Colour.dark_gold(),
                                  title=self.bot.get_message('top_embed_title'))
        description = ""
        for user in query:
            member = server.get_member(user.member_id)
            description += '%s\n' % self.bot.get_message('top_embed_line', member.display_name, user.balance)
        top_embed.description = description

        return top_embed

    def companies_top(self):
        session = self.create_session()
        query = session.query(self.company_model).order_by(self.company_model.balance.desc()).limit(10)

        session.close()

        top_embed = discord.Embed(color=discord.colour.Colour.dark_gold(),
                                  title=self.bot.get_message('companies_top_embed_title'))
        description = ""
        for company in query:
            description += '%s\n' % self.bot.get_message('companies_top_embed_line', company.name, company.balance)
        top_embed.description = description

        return top_embed

    def company_top_donors(self, company_name: str):
        session = self.create_session()
        query = session.query(self.company_model, self.user_model).filter_by(name=company_name)\
            .filter(self.user_model.company_donations > 0).order_by(self.user_model.company_donations.desc()).limit(10)

        session.close()

        result = list()
        for q in query:
            result.append((q[1].member_id, q[1].company_donations))
        return result

    async def buy_service(self, server: discord.Guild, member: discord.Member, service_name: str, force: bool):
        session = self.create_session()

        services = self.bot.cfg['Services']
        cost = services[service_name]['cost']
        notify_to = services[service_name]['notify_to']
        private_channel_name = services[service_name]['private_channel_name']
        role_to_add = services[service_name]['role_to_add']

        query = session.query(self.user_model).filter_by(member_id=member.id)
        if query.count() == 1:
            if force or query[0].balance >= cost:
                new_amount = query[0].balance
                if not force:
                    new_amount = query[0].balance - cost
                    query[0].balance = new_amount

                    session.commit()

                await self.bot.send_success_embed(server.get_channel(notify_to), 'service_buy_notification',
                                                  member.display_name, service_name)

                if len(private_channel_name) != 0:
                    overwrites = {
                        server.default_role: discord.PermissionOverwrite(read_messages=False),
                        member: discord.PermissionOverwrite(read_messages=True)
                    }
                    category = server.get_channel(self.bot.cfg['service_category'])
                    private_channel = await server.create_text_channel('%s - %s' %
                                                                       (member.display_name, private_channel_name),
                                                                       overwrites=overwrites)
                    if category is None:
                        await private_channel.edit(position=0)
                    else:
                        await private_channel.edit(category=category)
                    await self.bot.send_success_embed(private_channel, 'service_private_channel',
                                                      member.mention, service_name)
                if isinstance(role_to_add, int):
                    role = server.get_role(role_to_add)
                    await member.add_roles(role)
                return new_amount

        session.close()
        return -1

    async def buy_company_service(self, server: discord.Guild, member: discord.Member,
                                  company_name: str, service_name: str, force: bool):
        session = self.create_session()

        company_services = self.bot.cfg['CompanyServices']
        cost = company_services[service_name]['cost']
        notify_to = company_services[service_name]['notify_to']
        private_channel_name = company_services[service_name]['private_channel_name']

        query = session.query(self.company_model).filter_by(name=company_name.lower())
        if query.count() == 1:
            company_buyer = query[0]
            if force or company_buyer.balance >= cost:
                new_amount = company_buyer.balance
                if not force:
                    new_amount = company_buyer.balance - cost
                    company_buyer.balance = new_amount

                    session.commit()

                await self.bot.send_success_embed(server.get_channel(notify_to), 'company_service_buy_notification',
                                                  company_name, service_name)

                if len(private_channel_name) != 0:
                    # TODO Il canale dovrebbe essere visibile a tutto lo staff della Compagnia, ma non si possono usare
                    #  i ruoli perchè ora non sono più solo della singola Compagnia
                    overwrites = {
                        server.default_role: discord.PermissionOverwrite(read_messages=False),
                        member: discord.PermissionOverwrite(read_messages=True)
                    }
                    admin_mention = member.mention
                    category = server.get_channel(self.bot.cfg['company_service_category'])
                    private_channel = await server.create_text_channel('%s - %s' %
                                                                       (company_name, private_channel_name),
                                                                       overwrites=overwrites)
                    if category is None:
                        await private_channel.edit(position=0)
                    else:
                        await private_channel.edit(category=category)
                    await self.bot.send_success_embed(private_channel, 'service_private_channel',
                                                      admin_mention, service_name)

                return new_amount

        session.close()
        return -1
