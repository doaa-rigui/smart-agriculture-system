"""
Smart Agriculture Decision Support System - Backend
Production-grade FastAPI application with comprehensive error handling and explainability
"""

from fastapi import FastAPI, HTTPException, status
from pydantic import BaseModel, Field, validator
from contextlib import contextmanager
from typing import List, Optional, Dict
from datetime import datetime
from enum import Enum
import sqlite3
import logging

# ============================================================================
# CONFIGURATION
# ============================================================================

class Config:
    """Centralized configuration"""
    DATABASE_PATH = "agriculture.db"
    
    SENSOR_RANGES = {
        "soil_moisture": {"min": 0.0, "max": 100.0},
        "temperature": {"min": -20.0, "max": 60.0},
        "humidity": {"min": 0.0, "max": 100.0}
    }
    
    CROP_RULES = {
        "tomato": {
            "moisture_optimal_min": 60,
            "moisture_critical_min": 40,
            "moisture_max": 85,
            "temp_optimal_min": 20,
            "temp_optimal_max": 30
        },
        "lettuce": {
            "moisture_optimal_min": 70,
            "moisture_critical_min": 55,
            "moisture_max": 90,
            "temp_optimal_min": 15,
            "temp_optimal_max": 25
        }
    }
    
    DEFAULT_CROP = "tomato"

# ============================================================================
# LOGGING
# ============================================================================

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ============================================================================
# DATA MODELS
# ============================================================================

class SensorData(BaseModel):
    """Validated sensor data model"""
    soil_moisture: float = Field(..., ge=0, le=100)
    temperature: float = Field(..., ge=-20, le=60)
    humidity: float = Field(..., ge=0, le=100)
    
    @validator('soil_moisture', 'temperature', 'humidity')
    def validate_ranges(cls, v, field):
        field_name = field.name
        ranges = Config.SENSOR_RANGES.get(field_name)
        if ranges and not (ranges['min'] <= v <= ranges['max']):
            raise ValueError(f"{field_name} out of valid range")
        return v

class RecommendationType(str, Enum):
    IRRIGATION = "irrigation"
    FERTILIZATION = "fertilization"
    STATUS = "status"

class Recommendation(BaseModel):
    type: RecommendationType
    action: str
    reason: str
    urgency: str
    timestamp: str
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)

# ============================================================================
# DATABASE
# ============================================================================

class DatabaseManager:
    """Handles database connections with proper resource management"""
    
    @staticmethod
    @contextmanager
    def get_connection():
        conn = None
        try:
            conn = sqlite3.connect(Config.DATABASE_PATH)
            conn.row_factory = sqlite3.Row
            yield conn
            conn.commit()
        except sqlite3.Error as e:
            if conn:
                conn.rollback()
            logger.error(f"Database error: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Database operation failed"
            )
        finally:
            if conn:
                conn.close()
    
    @staticmethod
    def init_database():
        with DatabaseManager.get_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS sensor_data (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    soil_moisture REAL NOT NULL,
                    temperature REAL NOT NULL,
                    humidity REAL NOT NULL,
                    crop_type TEXT DEFAULT 'tomato'
                )
            ''')
            
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS recommendations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    recommendation_type TEXT NOT NULL,
                    action TEXT NOT NULL,
                    reason TEXT NOT NULL,
                    urgency TEXT NOT NULL,
                    confidence REAL DEFAULT 1.0,
                    sensor_data_id INTEGER,
                    FOREIGN KEY (sensor_data_id) REFERENCES sensor_data(id)
                )
            ''')

class SensorDataRepository:
    """Repository for sensor data operations"""
    
    @staticmethod
    def insert(data: SensorData, crop_type: str = Config.DEFAULT_CROP) -> int:
        with DatabaseManager.get_connection() as conn:
            cursor = conn.cursor()
            timestamp = datetime.now().isoformat()
            
            cursor.execute('''
                INSERT INTO sensor_data (timestamp, soil_moisture, temperature, humidity, crop_type)
                VALUES (?, ?, ?, ?, ?)
            ''', (timestamp, data.soil_moisture, data.temperature, data.humidity, crop_type))
            
            logger.info(f"Inserted sensor data: moisture={data.soil_moisture}%")
            return cursor.lastrowid
    
    @staticmethod
    def get_latest() -> Optional[Dict]:
        with DatabaseManager.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT id, timestamp, soil_moisture, temperature, humidity, crop_type
                FROM sensor_data
                ORDER BY id DESC
                LIMIT 1
            ''')
            
            row = cursor.fetchone()
            return dict(row) if row else None
    
    @staticmethod
    def get_history(limit: int = 100) -> List[Dict]:
        with DatabaseManager.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT timestamp, soil_moisture, temperature, humidity, crop_type
                FROM sensor_data
                ORDER BY id DESC
                LIMIT ?
            ''', (limit,))
            
            return [dict(row) for row in cursor.fetchall()]

class RecommendationRepository:
    """Repository for recommendation operations"""
    
    @staticmethod
    def insert(recommendation: Recommendation, sensor_data_id: int):
        with DatabaseManager.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO recommendations 
                (timestamp, recommendation_type, action, reason, urgency, confidence, sensor_data_id)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (
                recommendation.timestamp,
                recommendation.type.value,
                recommendation.action,
                recommendation.reason,
                recommendation.urgency,
                recommendation.confidence,
                sensor_data_id
            ))

# ============================================================================
# BUSINESS LOGIC
# ============================================================================

class DecisionEngine:
    """Core recommendation logic with explainability"""
    
    @staticmethod
    def evaluate_irrigation(sensor_data: Dict) -> Optional[Recommendation]:
        crop_type = sensor_data.get("crop_type", Config.DEFAULT_CROP)
        rules = Config.CROP_RULES[crop_type]
        moisture = sensor_data["soil_moisture"]
        
        timestamp = datetime.now().isoformat()
        
        # Critical drought
        if moisture < rules["moisture_critical_min"]:
            water_deficit = rules["moisture_optimal_min"] - moisture
            irrigation_amount = water_deficit * 0.5
            
            return Recommendation(
                type=RecommendationType.IRRIGATION,
                action=f"Irrigate immediately with {irrigation_amount:.1f}mm water",
                reason=(
                    f"**Critical Water Stress Detected**\n\n"
                    f"Your {crop_type} plants are below critical moisture threshold.\n"
                    f"- Current: {moisture}%\n"
                    f"- Critical: {rules['moisture_critical_min']}%\n"
                    f"- Optimal: {rules['moisture_optimal_min']}-{rules['moisture_max']}%\n\n"
                    f"**Impact:** Plants may wilt within 24 hours.\n"
                    f"**Action:** Apply {irrigation_amount:.1f}mm water within 6 hours.\n"
                    f"**Best Time:** Early morning (6-8 AM)."
                ),
                urgency="high",
                timestamp=timestamp,
                confidence=0.95
            )
        
        # Overwatering risk
        if moisture > rules["moisture_max"]:
            return Recommendation(
                type=RecommendationType.IRRIGATION,
                action="Stop all irrigation immediately",
                reason=(
                    f"**Overwatering Risk Detected**\n\n"
                    f"Soil moisture ({moisture}%) exceeds safe levels.\n"
                    f"- Maximum: {rules['moisture_max']}%\n\n"
                    f"**Risks:** Root rot, fungal diseases\n"
                    f"**Action:** Stop irrigation, allow soil to dry to {rules['moisture_optimal_min']}%."
                ),
                urgency="medium",
                timestamp=timestamp,
                confidence=0.90
            )
        
        return None
    
    @staticmethod
    def evaluate_fertilization(sensor_data: Dict) -> Optional[Recommendation]:
        crop_type = sensor_data.get("crop_type", Config.DEFAULT_CROP)
        rules = Config.CROP_RULES[crop_type]
        moisture = sensor_data["soil_moisture"]
        temp = sensor_data["temperature"]
        
        timestamp = datetime.now().isoformat()
        
        # Optimal conditions
        if (rules["temp_optimal_min"] <= temp <= rules["temp_optimal_max"] and 
            moisture > rules["moisture_optimal_min"]):
            
            return Recommendation(
                type=RecommendationType.FERTILIZATION,
                action="Apply nitrogen-rich fertilizer",
                reason=(
                    f"**Optimal Conditions for Fertilization**\n\n"
                    f"Current conditions favor nutrient uptake:\n"
                    f"- Temperature: {temp}°C (optimal: {rules['temp_optimal_min']}-{rules['temp_optimal_max']}°C)\n"
                    f"- Moisture: {moisture}% (adequate)\n\n"
                    f"**Recommendation:** Apply 20-30 kg/ha nitrogen fertilizer.\n"
                    f"**Best Time:** Early morning or late afternoon."
                ),
                urgency="low",
                timestamp=timestamp,
                confidence=0.80
            )
        
        return None

# ============================================================================
# API
# ============================================================================

app = FastAPI(
    title="Smart Agriculture API",
    description="Decision support system for precision agriculture",
    version="1.0.0"
)

@app.on_event("startup")
def startup_event():
    DatabaseManager.init_database()
    logger.info("Database initialized")

@app.post("/api/sensors/data", status_code=status.HTTP_201_CREATED)
def ingest_sensor_data(data: SensorData, crop_type: str = Config.DEFAULT_CROP):
    """Ingest sensor data with validation"""
    try:
        sensor_id = SensorDataRepository.insert(data, crop_type)
        return {
            "status": "success",
            "sensor_id": sensor_id,
            "timestamp": datetime.now().isoformat()
        }
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))
    except Exception as e:
        logger.error(f"Error in data ingestion: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal server error")

@app.get("/api/sensors/latest")
def get_latest_sensor_data():
    """Retrieve most recent sensor reading"""
    try:
        data = SensorDataRepository.get_latest()
        if not data:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No sensor data available")
        return data
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving sensor data: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal server error")

@app.get("/api/recommendations", response_model=List[Recommendation])
def get_recommendations():
    """Generate recommendations based on current sensor data"""
    try:
        sensor_data = SensorDataRepository.get_latest()
        if not sensor_data:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No sensor data available")
        
        recommendations = []
        
        # Evaluate irrigation
        irrigation_rec = DecisionEngine.evaluate_irrigation(sensor_data)
        if irrigation_rec:
            recommendations.append(irrigation_rec)
            RecommendationRepository.insert(irrigation_rec, sensor_data["id"])
        
        # Evaluate fertilization
        fert_rec = DecisionEngine.evaluate_fertilization(sensor_data)
        if fert_rec:
            recommendations.append(fert_rec)
            RecommendationRepository.insert(fert_rec, sensor_data["id"])
        
        # Default status
        if not recommendations:
            recommendations.append(Recommendation(
                type=RecommendationType.STATUS,
                action="All systems normal",
                reason="All parameters within optimal ranges.",
                urgency="none",
                timestamp=datetime.now().isoformat(),
                confidence=1.0
            ))
        
        return recommendations
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating recommendations: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal server error")

@app.get("/api/sensors/history")
def get_sensor_history(limit: int = 100):
    """Retrieve historical sensor readings"""
    try:
        if limit > 1000:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Limit cannot exceed 1000")
        history = SensorDataRepository.get_history(limit)
        return {"data": history, "count": len(history)}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving history: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal server error")

@app.get("/health")
def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
