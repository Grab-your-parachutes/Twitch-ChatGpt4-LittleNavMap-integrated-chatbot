# File: database_manager.py
import logging
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase, AsyncIOMotorCollection
from pymongo.errors import PyMongoError, ConnectionFailure, OperationFailure
from pymongo import ASCENDING, DESCENDING, IndexModel
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from dataclasses import dataclass
import asyncio
from config import Config

@dataclass
class DatabaseMetrics:
    total_conversations: int = 0
    active_users: int = 0
    average_response_time: float = 0.0
    storage_size: int = 0
    last_backup_time: Optional[datetime] = None
    total_users: int = 0
    total_flight_records: int = 0

class CollectionNames:
    CONVERSATIONS = "conversations"
    USERS = "users"
    COMMANDS = "commands"
    METRICS = "metrics"
    BACKUPS = "backups"
    FLIGHT_DATA = "flight_data"
    ALERTS = "alerts"

class DatabaseManager:
    def __init__(self, config: Config):
        self.config = config
        self.logger = logging.getLogger('DatabaseManager')
        self.client: Optional[AsyncIOMotorClient] = None
        self.db: Optional[AsyncIOMotorDatabase] = None
        self.collections: Dict[str, AsyncIOMotorCollection] = {}
        self.metrics = DatabaseMetrics()
        self._connection_retries = 0
        self._max_retries = 3
        self._retry_delay = 5
        self._connected = asyncio.Event()
        self._backup_task: Optional[asyncio.Task] = None
        self._metrics_task: Optional[asyncio.Task] = None

    async def connect(self) -> None:
        """Connect to MongoDB with retry mechanism."""
        while self._connection_retries < self._max_retries:
            try:
                self.client = AsyncIOMotorClient(
                    self.config.database.URI,
                    maxPoolSize=self.config.database.MAX_POOL_SIZE,
                    serverSelectionTimeoutMS=self.config.database.TIMEOUT_MS
                )
                
                # Test the connection
                await self.client.admin.command('ping')
                
                self.db = self.client[self.config.database.DB_NAME]
                await self._initialize_collections()
                await self.ensure_indexes()
                
                self._connected.set()
                self.logger.info("Successfully connected to MongoDB")
                
                # Start background tasks
                self._backup_task = asyncio.create_task(self._periodic_backup())
                self._metrics_task = asyncio.create_task(self._periodic_metrics_update())
                
                return
                
            except ConnectionFailure as e:
                self._connection_retries += 1
                self.logger.error(f"Connection attempt {self._connection_retries} failed: {e}")
                if self._connection_retries < self._max_retries:
                    await asyncio.sleep(self._retry_delay)
                else:
                    raise ConnectionFailure("Max connection retries reached")

    async def _initialize_collections(self) -> None:
        """Initialize all required collections."""
        self.collections = {
            CollectionNames.CONVERSATIONS: self.db[CollectionNames.CONVERSATIONS],
            CollectionNames.USERS: self.db[CollectionNames.USERS],
            CollectionNames.COMMANDS: self.db[CollectionNames.COMMANDS],
            CollectionNames.METRICS: self.db[CollectionNames.METRICS],
            CollectionNames.BACKUPS: self.db[CollectionNames.BACKUPS],
            CollectionNames.FLIGHT_DATA: self.db[CollectionNames.FLIGHT_DATA],
            CollectionNames.ALERTS: self.db[CollectionNames.ALERTS]
        }

    async def ensure_indexes(self) -> None:
        """Create and maintain database indexes."""
        try:
            indexes = {
                CollectionNames.CONVERSATIONS: [
                    IndexModel([("timestamp", DESCENDING)]),
                    IndexModel([("user", ASCENDING), ("timestamp", DESCENDING)])
                ],
                CollectionNames.USERS: [
                    IndexModel([("username", ASCENDING)], unique=True),
                    IndexModel([("last_seen", DESCENDING)])
                ],
                CollectionNames.COMMANDS: [
                    IndexModel([("name", ASCENDING)], unique=True),
                    IndexModel([("usage_count", DESCENDING)])
                ],
                CollectionNames.FLIGHT_DATA: [
                    IndexModel([("timestamp", DESCENDING)]),
                    IndexModel([("flight_id", ASCENDING)])
                ],
                CollectionNames.ALERTS: [
                    IndexModel([("name", ASCENDING)], unique=True),
                    IndexModel([("created_at", DESCENDING)])
                ]
            }
            
            for collection_name, collection_indexes in indexes.items():
                await self.collections[collection_name].create_indexes(collection_indexes)
            
            self.logger.info("Database indexes created successfully")
        except OperationFailure as e:
            self.logger.error(f"Failed to create indexes: {e}")
            raise

    async def save_conversation(self, user_message: str, bot_response: str, 
                              metadata: Optional[Dict[str, Any]] = None) -> str:
        """Save a conversation with additional metadata."""
        await self._connected.wait()
        
        try:
            document = {
                'user': user_message,
                'bot': bot_response,
                'timestamp': datetime.utcnow(),
                'metadata': metadata or {},
                'response_time': metadata.get('response_time') if metadata else None
            }
            
            result = await self.collections[CollectionNames.CONVERSATIONS].insert_one(document)
            return str(result.inserted_id)
            
        except PyMongoError as e:
            self.logger.error(f"Failed to save conversation: {e}")
            raise

    async def get_conversation_history(self, 
                                     user: Optional[str] = None,
                                     limit: int = 5,
                                     skip: int = 0,
                                     start_date: Optional[datetime] = None,
                                     end_date: Optional[datetime] = None) -> List[Dict[str, Any]]:
        """Get conversation history with advanced filtering."""
        await self._connected.wait()
        
        query = {}
        if user:
            query['user'] = user
        if start_date or end_date:
            query['timestamp'] = {}
            if start_date:
                query['timestamp']['$gte'] = start_date
            if end_date:
                query['timestamp']['$lte'] = end_date

        try:
            cursor = self.collections[CollectionNames.CONVERSATIONS].find(query)
            cursor.sort('timestamp', DESCENDING).skip(skip).limit(limit)
            return await cursor.to_list(length=limit)
        except PyMongoError as e:
            self.logger.error(f"Failed to retrieve conversation history: {e}")
            raise

    async def save_flight_data(self, flight_data: Dict[str, Any]) -> str:
        """Save flight simulation data."""
        await self._connected.wait()
        
        try:
            document = {
                **flight_data,
                'timestamp': datetime.utcnow()
            }
            result = await self.collections[CollectionNames.FLIGHT_DATA].insert_one(document)
            return str(result.inserted_id)
        except PyMongoError as e:
            self.logger.error(f"Failed to save flight data: {e}")
            raise

    async def save_alert(self, name: str, message: str) -> None:
        """Save a custom alert."""
        await self._connected.wait()
        
        try:
            document = {
                'name': name,
                'message': message,
                'created_at': datetime.utcnow()
            }
            await self.collections[CollectionNames.ALERTS].update_one(
                {'name': name},
                {'$set': document},
                upsert=True
            )
        except PyMongoError as e:
            self.logger.error(f"Failed to save alert: {e}")
            raise

    async def get_alert(self, name: str) -> Optional[Dict[str, Any]]:
        """Retrieve an alert by name."""
        await self._connected.wait()
        
        try:
            return await self.collections[CollectionNames.ALERTS].find_one({'name': name})
        except PyMongoError as e:
            self.logger.error(f"Failed to retrieve alert: {e}")
            raise

    async def delete_alert(self, name: str) -> bool:
        """Delete an alert."""
        await self._connected.wait()
        
        try:
            result = await self.collections[CollectionNames.ALERTS].delete_one({'name': name})
            return result.deleted_count > 0
        except PyMongoError as e:
            self.logger.error(f"Failed to delete alert: {e}")
            raise

    async def _periodic_backup(self) -> None:
        """Perform periodic database backups."""
        while True:
            try:
                await asyncio.sleep(3600)  # Backup every hour
                await self._create_backup()
            except Exception as e:
                self.logger.error(f"Backup failed: {e}")

    async def _create_backup(self) -> None:
        """Create a database backup."""
        try:
            collections_data = {}
            for name, collection in self.collections.items():
                if name != CollectionNames.BACKUPS:  # Don't backup the backups
                    data = await collection.find().to_list(length=None)
                    collections_data[name] = data

            backup_doc = {
                'timestamp': datetime.utcnow(),
                'data': collections_data,
                'metadata': {
                    'version': '1.0',
                    'collections': list(collections_data.keys())
                }
            }

            await self.collections[CollectionNames.BACKUPS].insert_one(backup_doc)
            self.metrics.last_backup_time = datetime.utcnow()
            self.logger.info("Database backup created successfully")
            
        except PyMongoError as e:
            self.logger.error(f"Failed to create backup: {e}")
            raise

    async def _periodic_metrics_update(self) -> None:
        """Update database metrics periodically."""
        while True:
            try:
                await asyncio.sleep(300)  # Update every 5 minutes
                await self._update_metrics()
            except Exception as e:
                self.logger.error(f"Metrics update failed: {e}")

    async def _update_metrics(self) -> None:
        """Update database metrics."""
        try:
            self.metrics.total_conversations = await self.collections[
                CollectionNames.CONVERSATIONS].count_documents({})
            
            self.metrics.active_users = len(await self.collections[
                CollectionNames.CONVERSATIONS].distinct('user'))
            
            pipeline = [
                {'$match': {'response_time': {'$exists': True}}},
                {'$group': {'_id': None, 'avg_time': {'$avg': '$response_time'}}}
            ]
            result = await self.collections[CollectionNames.CONVERSATIONS].aggregate(
                pipeline).to_list(length=1)
            if result:
                self.metrics.average_response_time = result[0]['avg_time']

            stats = await self.db.command('dbStats')
            self.metrics.storage_size = stats['storageSize']
            
            self.metrics.total_users = await self.collections[
                CollectionNames.USERS].count_documents({})
            
            self.metrics.total_flight_records = await self.collections[
                CollectionNames.FLIGHT_DATA].count_documents({})

        except PyMongoError as e:
            self.logger.error(f"Failed to update metrics: {e}")
            raise

    async def close(self) -> None:
        """Close database connection and cleanup."""
        if self._backup_task:
            self._backup_task.cancel()
        if self._metrics_task:
            self._metrics_task.cancel()
            
        try:
            if self._backup_task:
                await self._backup_task
            if self._metrics_task:
                await self._metrics_task
        except asyncio.CancelledError:
            pass

        if self.client:
            self.client.close()
            self._connected.clear()
            self.logger.info("Database connection closed")

    async def __aenter__(self):
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()