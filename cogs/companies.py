import discord
from discord.ext import commands
from sqlalchemy.orm import Session

from database import Database


class Companies(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.user_model: Database.User.__class__ = self.bot.db.User
        self.company_model: Database.Company.__class__ = self.bot.db.Company

    def create_session(self) -> Session:
        return self.bot.db.Session()

    def is_staff(self, member: discord.Member):
        if self.bot.company_staff_roles['governatore'] in member.roles \
                or self.bot.company_staff_roles['console'] in member.roles:
            return True
        return False

    def get_company_for(self, member: discord.Member):
        session = self.create_session()
        query = session.query(self.user_model).filter_by(member_id=member.id)

        session.close()

        if query.count() == 1:
            return query[0].company_name
        else:
            return None
