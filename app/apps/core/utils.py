"""
Utilitários gerais para o app core.
"""
from datetime import datetime, timedelta
from django.utils import timezone


def calculate_video_delivery_deadline(
    requested_at: datetime,
    base_hours: int = 48,
    include_weekends: bool = False,
    business_hours_only: bool = True
) -> datetime:
    """
    Calcula prazo de entrega para vídeo avatar com regras de horário comercial.
    
    Lógica em 3 etapas:
    1. NORMALIZAR: Ajustar solicitação para horário comercial (9h-18h, seg-sex)
    2. ADICIONAR: Somar 48 horas corridas ao horário normalizado
    3. AJUSTAR: Se resultado caiu fora do comercial, ajustar novamente
    
    Exemplos:
        - Qui 17h → Sexta 9h + 48h = Dom 9h → Segunda 9h (ajustado)
        - Seg 10h → Seg 10h + 48h = Qua 10h (sem ajuste)
        - Sáb 14h → Seg 9h + 48h = Qua 9h (normalizado + 48h)
    
    Args:
        requested_at: Data/hora da solicitação do vídeo
        base_hours: Horas base para cálculo (padrão: 48)
        include_weekends: Se True, não pula fins de semana (padrão: False)
        business_hours_only: Se True, respeita 9h-18h (padrão: True)
    
    Returns:
        datetime: Prazo estimado de entrega
    """
    # Garantir timezone aware
    if not requested_at.tzinfo:
        requested_at = timezone.make_aware(requested_at)
    
    # ===== ETAPA 1: NORMALIZAR HORÁRIO DE INÍCIO =====
    start_time = requested_at
    day_of_week = start_time.weekday()  # 0=Segunda, 6=Domingo
    hour = start_time.hour
    
    # Fim de semana → próxima segunda 9h
    if not include_weekends and day_of_week >= 5:  # Sáb=5, Dom=6
        days_to_add = 1 if day_of_week == 6 else 2  # Dom=1, Sáb=2
        start_time = start_time + timedelta(days=days_to_add)
        start_time = start_time.replace(hour=9, minute=0, second=0, microsecond=0)
    
    # Antes das 9h → ajustar para 9h do mesmo dia
    elif business_hours_only and hour < 9:
        start_time = start_time.replace(hour=9, minute=0, second=0, microsecond=0)
    
    # Depois das 17h → próximo dia útil 9h
    elif business_hours_only and hour >= 17:
        start_time = start_time + timedelta(days=1)
        start_time = start_time.replace(hour=9, minute=0, second=0, microsecond=0)
        
        # Se próximo dia for fim de semana, pular para segunda
        if not include_weekends:
            while start_time.weekday() >= 5:
                start_time = start_time + timedelta(days=1)
    
    # ===== ETAPA 2: ADICIONAR HORAS CORRIDAS =====
    deadline = start_time + timedelta(hours=base_hours)
    
    # ===== ETAPA 3: AJUSTAR RESULTADO PARA HORÁRIO COMERCIAL =====
    final_day = deadline.weekday()
    final_hour = deadline.hour
    
    # Se caiu em fim de semana → próxima segunda 9h
    if not include_weekends and final_day >= 5:
        days_to_add = 1 if final_day == 6 else 2
        deadline = deadline + timedelta(days=days_to_add)
        deadline = deadline.replace(hour=9, minute=0, second=0, microsecond=0)
    
    # Se antes das 9h → ajustar para 9h do mesmo dia
    elif business_hours_only and final_hour < 9:
        deadline = deadline.replace(hour=9, minute=0, second=0, microsecond=0)
    
    # Se depois das 17h → próximo dia útil 9h
    elif business_hours_only and final_hour >= 17:
        deadline = deadline + timedelta(days=1)
        deadline = deadline.replace(hour=9, minute=0, second=0, microsecond=0)
        
        # Se próximo dia for fim de semana, pular para segunda
        if not include_weekends:
            while deadline.weekday() >= 5:
                deadline = deadline + timedelta(days=1)
    
    return deadline
