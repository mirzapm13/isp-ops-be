from sqlalchemy import Column, Integer, String, Numeric, Date, TIMESTAMP
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql import func

Base = declarative_base()

class BillingCustomer(Base):
    __tablename__ = "billing_customers"

    id = Column(Integer, primary_key=True, index=True)

    id_pelanggan = Column(String, index=True,nullable=False)
    ip_secret = Column(String)
    tlp = Column(String, nullable=False)
    alamat = Column(String)

    nama_pelanggan = Column(String)
    nama_langganan = Column(String)
    harga = Column(Numeric)

    status_langganan = Column(String)
    jatuh_tempo = Column(Date)

    nama_router = Column(String)
    id_olt = Column(String)
    id_odp = Column(String)

    source_file = Column(String)
    imported_at = Column(TIMESTAMP, server_default=func.now())

    def to_dict(self):
        return {
            "id": self.id,
            "id_pelanggan": self.id_pelanggan,
            "ip_secret": self.ip_secret,
            "nama_pelanggan": self.nama_pelanggan,
            "nama_langganan": self.nama_langganan,
            "harga": self.harga,
            "status_langganan": self.status_langganan,
            "jatuh_tempo": self.jatuh_tempo,
            "nama_router": self.nama_router,
            "id_olt": self.id_olt,
            "id_odp": self.id_odp,
            "source_file": self.source_file,
            "imported_at": self.imported_at,
        }
