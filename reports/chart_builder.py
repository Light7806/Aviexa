"""
reports/chart_builder.py
Generate matplotlib charts for Aviexa PDF reports.
"""

import matplotlib
matplotlib.use('Agg')  # Non-GUI backend for server environments

import matplotlib.pyplot as plt
import numpy as np
from pathlib import Path
from typing import List, Optional, Dict, Any
import logging

from anomaly.models import TelemetryEvent, AnomalyEvent, EventType

logger = logging.getLogger(__name__)


class ChartBuilder:
    """
    Builds charts from telemetry data for PDF reports.
    
    Features:
    - Loss curves with anomaly markers
    - Gradient norm curves
    - Memory usage curves
    - Handles missing data gracefully
    """
    
    def __init__(self, figsize=(10, 6), dpi=100):
        """
        Initialize chart builder.
        
        Args:
            figsize: Figure size (width, height) in inches
            dpi: Dots per inch for output
        """
        self.figsize = figsize
        self.dpi = dpi
    
    def build_loss_chart(
        self,
        events: List[TelemetryEvent],
        anomalies: List[AnomalyEvent],
        output_path: Path
    ) -> bool:
        """
        Build loss curve chart with anomaly markers.
        
        Args:
            events: Telemetry events
            anomalies: Detected anomalies
            output_path: Path to save chart
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Extract loss events
            loss_events = [e for e in events if e.event_type == EventType.LOSS]
            
            if not loss_events:
                logger.warning("No loss events found, skipping loss chart")
                return False
            
            # Extract data
            steps = [e.step for e in loss_events]
            # LossEvent has loss_value attribute, fallback to payload
            losses = []
            for e in loss_events:
                loss_val = getattr(e, 'loss_value', None)
                if loss_val is not None:
                    losses.append(loss_val)
                else:
                    losses.append(e.payload.get('loss_value', e.payload.get('loss', 0)))
            
            # Create figure
            fig, ax = plt.subplots(figsize=self.figsize, dpi=self.dpi)
            
            # Plot loss curve
            ax.plot(steps, losses, 'b-', linewidth=2, label='Training Loss')
            
            # Mark anomalies
            loss_anomalies = [a for a in anomalies if 'loss' in a.anomaly_type.lower()]
            if loss_anomalies:
                anomaly_steps = [a.step for a in loss_anomalies]
                anomaly_losses = []
                for a_step in anomaly_steps:
                    # Find closest loss value
                    closest_idx = min(range(len(steps)), key=lambda i: abs(steps[i] - a_step))
                    anomaly_losses.append(losses[closest_idx])
                
                ax.scatter(anomaly_steps, anomaly_losses, c='red', s=100, 
                          marker='x', linewidths=3, label='Anomalies', zorder=5)
            
            # Styling
            ax.set_xlabel('Training Step', fontsize=12)
            ax.set_ylabel('Loss', fontsize=12)
            ax.set_title('Training Loss Curve', fontsize=14, fontweight='bold')
            ax.legend(loc='best')
            ax.grid(True, alpha=0.3)
            
            # Save
            plt.tight_layout()
            plt.savefig(output_path, dpi=self.dpi, bbox_inches='tight')
            plt.close(fig)
            
            logger.info(f"Loss chart saved to {output_path}")
            return True
            
        except Exception as e:
            logger.error(f"Error building loss chart: {e}")
            return False
    
    def build_gradient_chart(
        self,
        events: List[TelemetryEvent],
        anomalies: List[AnomalyEvent],
        output_path: Path
    ) -> bool:
        """
        Build gradient norm chart with anomaly markers.
        
        Args:
            events: Telemetry events
            anomalies: Detected anomalies
            output_path: Path to save chart
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Extract backward events with gradient norms
            backward_events = [e for e in events if e.event_type == EventType.BACKWARD]
            
            if not backward_events:
                logger.warning("No backward events found, skipping gradient chart")
                return False
            
            # Extract data
            steps = [e.step for e in backward_events]
            # BackwardEvent has gradient_norm attribute, fallback to payload
            grad_norms = []
            for e in backward_events:
                grad_norm = getattr(e, 'gradient_norm', None)
                if grad_norm is not None:
                    grad_norms.append(grad_norm)
                else:
                    grad_norms.append(e.payload.get('gradient_norm', e.payload.get('grad_norm', 0)))
            
            # Create figure
            fig, ax = plt.subplots(figsize=self.figsize, dpi=self.dpi)
            
            # Plot gradient norms
            ax.plot(steps, grad_norms, 'g-', linewidth=2, label='Gradient Norm')
            
            # Mark gradient anomalies
            grad_anomalies = [a for a in anomalies if 'gradient' in a.anomaly_type.lower()]
            if grad_anomalies:
                anomaly_steps = [a.step for a in grad_anomalies]
                anomaly_norms = []
                for a_step in anomaly_steps:
                    # Find closest norm value
                    closest_idx = min(range(len(steps)), key=lambda i: abs(steps[i] - a_step))
                    anomaly_norms.append(grad_norms[closest_idx])
                
                ax.scatter(anomaly_steps, anomaly_norms, c='red', s=100,
                          marker='x', linewidths=3, label='Anomalies', zorder=5)
            
            # Styling
            ax.set_xlabel('Training Step', fontsize=12)
            ax.set_ylabel('Gradient Norm', fontsize=12)
            ax.set_title('Gradient Norm Over Time', fontsize=14, fontweight='bold')
            ax.legend(loc='best')
            ax.grid(True, alpha=0.3)
            ax.set_yscale('log')  # Log scale for gradient norms
            
            # Save
            plt.tight_layout()
            plt.savefig(output_path, dpi=self.dpi, bbox_inches='tight')
            plt.close(fig)
            
            logger.info(f"Gradient chart saved to {output_path}")
            return True
            
        except Exception as e:
            logger.error(f"Error building gradient chart: {e}")
            return False
    
    def build_memory_chart(
        self,
        events: List[TelemetryEvent],
        anomalies: List[AnomalyEvent],
        output_path: Path
    ) -> bool:
        """
        Build memory usage chart.
        
        Args:
            events: Telemetry events
            anomalies: Detected anomalies
            output_path: Path to save chart
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Extract memory events
            memory_events = [e for e in events if e.event_type == EventType.MEMORY]
            
            if not memory_events:
                logger.warning("No memory events found, skipping memory chart")
                return False
            
            # Extract data
            steps = [e.step for e in memory_events]
            # MemoryEvent has cpu_allocated_mb and cuda_allocated_mb, use total or fallback
            memory_mb = []
            for e in memory_events:
                cpu_mb = getattr(e, 'cpu_allocated_mb', None) or 0
                cuda_mb = getattr(e, 'cuda_allocated_mb', None) or 0
                total_mb = cpu_mb + cuda_mb
                if total_mb == 0:
                    # Fallback to payload
                    total_mb = e.payload.get('memory_mb', e.payload.get('total_mb', 0))
                memory_mb.append(total_mb)
            
            # Create figure
            fig, ax = plt.subplots(figsize=self.figsize, dpi=self.dpi)
            
            # Plot memory usage
            ax.plot(steps, memory_mb, 'm-', linewidth=2, label='Memory Usage')
            
            # Mark memory anomalies
            mem_anomalies = [a for a in anomalies if 'memory' in a.anomaly_type.lower()]
            if mem_anomalies:
                anomaly_steps = [a.step for a in mem_anomalies]
                anomaly_memory = []
                for a_step in anomaly_steps:
                    # Find closest memory value
                    closest_idx = min(range(len(steps)), key=lambda i: abs(steps[i] - a_step))
                    anomaly_memory.append(memory_mb[closest_idx])
                
                ax.scatter(anomaly_steps, anomaly_memory, c='red', s=100,
                          marker='x', linewidths=3, label='Anomalies', zorder=5)
            
            # Styling
            ax.set_xlabel('Training Step', fontsize=12)
            ax.set_ylabel('Memory Usage (MB)', fontsize=12)
            ax.set_title('Memory Usage Over Time', fontsize=14, fontweight='bold')
            ax.legend(loc='best')
            ax.grid(True, alpha=0.3)
            
            # Save
            plt.tight_layout()
            plt.savefig(output_path, dpi=self.dpi, bbox_inches='tight')
            plt.close(fig)
            
            logger.info(f"Memory chart saved to {output_path}")
            return True
            
        except Exception as e:
            logger.error(f"Error building memory chart: {e}")
            return False
    
    def build_all_charts(
        self,
        session_record,
        output_dir: Path
    ) -> Dict[str, Optional[Path]]:
        """
        Build all available charts for a session.
        
        Args:
            session_record: SessionRecord with telemetry and anomalies
            output_dir: Directory to save charts
            
        Returns:
            Dictionary mapping chart type to file path (or None if not generated)
        """
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        
        results = {}
        
        # Loss chart
        loss_path = output_dir / "loss_curve.png"
        if self.build_loss_chart(session_record.telemetry_events,
                                 session_record.anomalies,
                                 loss_path):
            results['loss'] = loss_path
        else:
            results['loss'] = None

        # Gradient chart
        gradient_path = output_dir / "gradient_norm.png"
        if self.build_gradient_chart(session_record.telemetry_events,
                                     session_record.anomalies,
                                     gradient_path):
            results['gradient'] = gradient_path
        else:
            results['gradient'] = None

        # Memory chart
        memory_path = output_dir / "memory_usage.png"
        if self.build_memory_chart(session_record.telemetry_events,
                                   session_record.anomalies,
                                   memory_path):
            results['memory'] = memory_path
        else:
            results['memory'] = None

        return results


# Made with Bob
