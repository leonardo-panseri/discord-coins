import urllib
import urllib.parse

from sqlalchemy import Column, create_engine, Boolean, String, BigInteger, Float, ForeignKey, event, exc
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from sqlalchemy.pool import Pool


class Database:
    Base = declarative_base()

    def __init__(self, bot):
        self.bot = bot
        self.engine = create_engine(f'mysql+mysqldb://{self.bot.cfg["Database"]["user"]}:' + urllib.parse.quote_plus(self.bot.cfg["Database"]["password"]) + f'@{self.bot.cfg["Database"]["host"]}/{self.bot.cfg["Database"]["db"]}')
        self.Base = declarative_base()
        self.Session = sessionmaker(bind=self.engine)
        event.listen(Pool, "checkout", check_connection)

        self.create_tables()

    class User(Base):
        __tablename__ = "users"

        member_id = Column(BigInteger, primary_key=True)
        balance = Column(Float, nullable=False, default=0)
        blacklisted = Column(Boolean, nullable=False, default=False)
        company_name = Column(String(50), ForeignKey("companies.name", ondelete="SET NULL", onupdate="CASCADE"))
        company = relationship("Company", back_populates="members")
        company_donations = Column(Float, nullable=False, default=0)

        def __repr__(self):
            return f"<User(id='{self.member_id}', balance='{self.balance}')>"

    class Company(Base):
        __tablename__ = "companies"

        name = Column(String(50), primary_key=True)
        tag = Column(String(4), unique=True, nullable=False)
        category_id = Column(BigInteger, nullable=False)
        role = Column(BigInteger, nullable=False)
        faction = Column(String(50))
        balance = Column(Float, nullable=False, default=0)
        members = relationship("User", back_populates="company")

        def __repr__(self):
            return f"<Company(id='{self.name}', balance='{self.balance}')>"

    def create_tables(self):
        self.Base.metadata.create_all(self.engine)


@event.listens_for(Pool, "checkout")
def check_connection(dbapi_con, con_record, con_proxy):
    """Listener for Pool checkout events that pings every connection before using.
    Implements pessimistic disconnect handling strategy. See also:
    http://docs.sqlalchemy.org/en/rel_0_8/core/pooling.html#disconnect-handling-pessimistic"""

    cursor = dbapi_con.cursor()
    try:
        cursor.execute("SELECT 1")  # could also be dbapi_con.ping(),
    except exc.OperationalError as ex:
        if ex.args[0] in (2006,   # MySQL server has gone away
                          2013,   # Lost connection to MySQL server during query
                          2055):  # Lost connection to MySQL server at '%s', system error: %d
            # caught by pool, which will retry with a new connection
            raise exc.DisconnectionError()
        else:
            raise
