# app/store.py
"""
Persistent store using SQLAlchemy ORM for financial transactions.
"""
import os
from datetime import datetime, date, timedelta
from typing import Optional, Literal, List, Dict, Any
from decimal import Decimal
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, Date, Text, Index, func
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, scoped_session
from sqlalchemy.exc import SQLAlchemyError
from contextlib import contextmanager

Base = declarative_base()

class Transaction(Base):
    """Financial transaction model"""
    __tablename__ = 'transactions'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(100), nullable=False)
    amount = Column(Float, nullable=False)
    type = Column(String(10), nullable=False)  # 'income' or 'expense'
    category = Column(String(50), nullable=False)
    description = Column(Text, nullable=True)
    date = Column(Date, nullable=False, default=date.today)
    thread_id = Column(String(100), nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.now)
    updated_at = Column(DateTime, nullable=False, default=datetime.now, onupdate=datetime.now)
    
    # Indexes for performance
    __table_args__ = (
        Index('idx_user_date', 'user_id', 'date'),
        Index('idx_user_category', 'user_id', 'category'),
        Index('idx_user_type', 'user_id', 'type'),
        Index('idx_thread', 'thread_id'),
    )
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert transaction to plain dict"""
        return {
            'id': self.id,
            'user_id': self.user_id,
            'amount': float(self.amount),
            'type': self.type,
            'category': self.category,
            'description': self.description,
            'date': self.date.isoformat() if self.date else None,
            'thread_id': self.thread_id,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }


class CategoryMapping(Base):
    """Category auto-mapping model"""
    __tablename__ = 'category_mappings'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    keyword = Column(String(100), unique=True, nullable=False)
    category = Column(String(50), nullable=False)
    type = Column(String(10), nullable=False)  # 'income' or 'expense'
    
    __table_args__ = (
        Index('idx_keyword', 'keyword'),
    )


class PersistentSQLiteStore:
    """Persistent store based on SQLAlchemy to manage financial transactions"""
    
    # System default categories
    DEFAULT_CATEGORIES = {
        'expense': [
            'Alimentação', 'Transporte', 'Moradia', 'Saúde', 'Educação',
            'Lazer', 'Compras', 'Serviços', 'Assinaturas', 'Outros'
        ],
        'income': [
            'Salário', 'Freelance', 'Investimentos', 'Vendas', 
            'Reembolso', 'Presente', 'Outros'
        ]
    }
    
    # Keyword-to-category mapping
    CATEGORY_KEYWORDS = {
        # Despesas - Alimentação
        'almoço': ('Alimentação', 'expense'),
        'jantar': ('Alimentação', 'expense'),
        'café': ('Alimentação', 'expense'),
        'lanche': ('Alimentação', 'expense'),
        'restaurante': ('Alimentação', 'expense'),
        'mercado': ('Alimentação', 'expense'),
        'supermercado': ('Alimentação', 'expense'),
        'ifood': ('Alimentação', 'expense'),
        'delivery': ('Alimentação', 'expense'),
        
        # Despesas - Transporte
        'uber': ('Transporte', 'expense'),
        '99': ('Transporte', 'expense'),
        'taxi': ('Transporte', 'expense'),
        'ônibus': ('Transporte', 'expense'),
        'metrô': ('Transporte', 'expense'),
        'gasolina': ('Transporte', 'expense'),
        'combustível': ('Transporte', 'expense'),
        'estacionamento': ('Transporte', 'expense'),
        
        # Despesas - Moradia
        'aluguel': ('Moradia', 'expense'),
        'condomínio': ('Moradia', 'expense'),
        'luz': ('Moradia', 'expense'),
        'água': ('Moradia', 'expense'),
        'internet': ('Moradia', 'expense'),
        'gás': ('Moradia', 'expense'),
        
        # Despesas - Assinaturas
        'netflix': ('Assinaturas', 'expense'),
        'spotify': ('Assinaturas', 'expense'),
        'amazon': ('Assinaturas', 'expense'),
        'disney': ('Assinaturas', 'expense'),
        
        # Receitas
        'salário': ('Salário', 'income'),
        'freelance': ('Freelance', 'income'),
        'freela': ('Freelance', 'income'),
        'venda': ('Vendas', 'income'),
        'dividendos': ('Investimentos', 'income'),
        'rendimento': ('Investimentos', 'income'),
    }
    
    def __init__(self, db_path: str = "financial_store.db"):
        """Initialize store with SQLAlchemy"""
        self.db_path = db_path
        self.engine = create_engine(
            f'sqlite:///{db_path}',
            connect_args={'check_same_thread': False},
            echo=False  # Mude para True para debug
        )
        
        # Create tables if not exist
        Base.metadata.create_all(self.engine)
        
        # Create session factory
        self.SessionLocal = scoped_session(sessionmaker(
            autocommit=False,
            autoflush=False,
            bind=self.engine
        ))
        
        # Initialize category mappings
        self._init_category_mappings()
    
    @contextmanager
    def get_session(self):
        """Context manager for SQLAlchemy sessions"""
        session = self.SessionLocal()
        try:
            yield session
            session.commit()
        except SQLAlchemyError as e:
            session.rollback()
            raise e
        finally:
            session.close()
    
    def _init_category_mappings(self):
        """Initialize keyword mappings in the database"""
        with self.get_session() as session:
            for keyword, (category, trans_type) in self.CATEGORY_KEYWORDS.items():
                # Check if exists
                existing = session.query(CategoryMapping).filter_by(keyword=keyword).first()
                if not existing:
                    mapping = CategoryMapping(
                        keyword=keyword,
                        category=category,
                        type=trans_type
                    )
                    session.add(mapping)
    
    def infer_category(self, description: str) -> tuple[str, str]:
        """Infer category and type based on description"""
        if not description:
            return ('Outros', 'expense')
        
        description_lower = description.lower()
        
        with self.get_session() as session:
            # Buscar nos mapeamentos do banco
            for mapping in session.query(CategoryMapping).all():
                if mapping.keyword in description_lower:
                    return (mapping.category, mapping.type)
        
        # Padrão se não encontrar
        return ('Outros', 'expense')
    
    def add_transaction(
        self,
        user_id: str,
        amount: float,
        type: Literal["income", "expense"],
        category: str,
        description: Optional[str] = None,
        transaction_date: Optional[date] = None,
        thread_id: Optional[str] = None
    ) -> int:
        """Add a new transaction"""
        with self.get_session() as session:
            transaction = Transaction(
                user_id=user_id,
                amount=abs(amount),  # Sempre positivo
                type=type,
                category=category,
                description=description,
                date=transaction_date or date.today(),
                thread_id=thread_id
            )
            session.add(transaction)
            session.flush()  # Para obter o ID
            return transaction.id
    
    def get_balance(
        self,
        user_id: str,
        period: Literal["today", "week", "month", "year", "all"] = "month"
    ) -> Dict[str, float]:
        """Get balance for a given period"""
        with self.get_session() as session:
            # Determine start date based on period
            today = date.today()
            if period == "today":
                start_date = today
            elif period == "week":
                start_date = today - timedelta(days=7)
            elif period == "month":
                start_date = today.replace(day=1)
            elif period == "year":
                start_date = today.replace(month=1, day=1)
            else:  # all
                start_date = date(2000, 1, 1)
            
            # Income query
            income = session.query(func.sum(Transaction.amount)).filter(
                Transaction.user_id == user_id,
                Transaction.type == 'income',
                Transaction.date >= start_date
            ).scalar() or 0.0
            
            # Expense query
            expenses = session.query(func.sum(Transaction.amount)).filter(
                Transaction.user_id == user_id,
                Transaction.type == 'expense',
                Transaction.date >= start_date
            ).scalar() or 0.0
            
            return {
                'income': float(income),
                'expenses': float(expenses),
                'balance': float(income - expenses),
                'period': period,
                'start_date': start_date.isoformat()
            }
    
    def list_transactions(
        self,
        user_id: str,
        limit: int = 10,
        type: Optional[Literal["income", "expense"]] = None,
        period: Optional[Literal["today", "week", "month", "year"]] = None,
        category: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """List transactions with optional filters"""
        with self.get_session() as session:
            query = session.query(Transaction).filter(
                Transaction.user_id == user_id
            )
            
            # Apply filters
            if type:
                query = query.filter(Transaction.type == type)
            
            if category:
                query = query.filter(Transaction.category == category)
            
            if period:
                today = date.today()
                if period == "today":
                    start_date = today
                elif period == "week":
                    start_date = today - timedelta(days=7)
                elif period == "month":
                    start_date = today.replace(day=1)
                elif period == "year":
                    start_date = today.replace(month=1, day=1)
                
                query = query.filter(Transaction.date >= start_date)
            
            # Order by date desc and apply limit
            transactions = query.order_by(Transaction.date.desc()).limit(limit).all()
            
            return [t.to_dict() for t in transactions]
    
    def get_category_summary(
        self,
        user_id: str,
        period: Literal["today", "week", "month", "year"] = "month"
    ) -> Dict[str, Dict[str, float]]:
        """Get summary grouped by category"""
        with self.get_session() as session:
            # Determine start date
            today = date.today()
            if period == "today":
                start_date = today
            elif period == "week":
                start_date = today - timedelta(days=7)
            elif period == "month":
                start_date = today.replace(day=1)
            else:  # year
                start_date = today.replace(month=1, day=1)
            
            # Aggregated query by category and type
            results = session.query(
                Transaction.category,
                Transaction.type,
                func.sum(Transaction.amount).label('total'),
                func.count(Transaction.id).label('count')
            ).filter(
                Transaction.user_id == user_id,
                Transaction.date >= start_date
            ).group_by(
                Transaction.category,
                Transaction.type
            ).all()
            
            summary = {
                'expenses': {},
                'income': {},
                'period': period,
                'start_date': start_date.isoformat()
            }
            
            for category, trans_type, total, count in results:
                category_data = {
                    'total': float(total),
                    'count': count,
                    'average': float(total / count) if count > 0 else 0
                }
                
                if trans_type == 'expense':
                    summary['expenses'][category] = category_data
                else:
                    summary['income'][category] = category_data
            
            return summary
    
    def delete_transaction(self, user_id: str, transaction_id: int) -> bool:
        """Delete a specific transaction"""
        with self.get_session() as session:
            transaction = session.query(Transaction).filter(
                Transaction.id == transaction_id,
                Transaction.user_id == user_id
            ).first()
            
            if transaction:
                session.delete(transaction)
                return True
            return False
    
    def update_transaction(
        self,
        user_id: str,
        transaction_id: int,
        **kwargs
    ) -> bool:
        """Update an existing transaction"""
        with self.get_session() as session:
            transaction = session.query(Transaction).filter(
                Transaction.id == transaction_id,
                Transaction.user_id == user_id
            ).first()
            
            if transaction:
                for key, value in kwargs.items():
                    if hasattr(transaction, key) and value is not None:
                        setattr(transaction, key, value)
                return True
            return False

    def clear_user_transactions(self, user_id: str) -> int:
        """Remove todas as transações do usuário e retorna a quantidade apagada."""
        with self.get_session() as session:
            deleted = session.query(Transaction).filter(
                Transaction.user_id == user_id
            ).delete(synchronize_session=False)
            return int(deleted)