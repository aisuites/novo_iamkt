"""
Validação e normalização de CPF brasileiro.
"""
import re


def normalize_cpf(value: str) -> str:
    """Remove qualquer caractere que não seja dígito. Ex: '123.456.789-09' -> '12345678909'."""
    return re.sub(r'\D', '', value or '')


def is_valid_cpf(value: str) -> bool:
    """
    Valida CPF pelos dígitos verificadores.
    Aceita CPF com ou sem máscara (pontos/traço).
    """
    cpf = normalize_cpf(value)

    # Deve ter 11 dígitos
    if len(cpf) != 11:
        return False

    # Rejeita sequências repetidas (00000000000, 11111111111, ...)
    if cpf == cpf[0] * 11:
        return False

    # Calcula os dois dígitos verificadores
    for digit_pos in (9, 10):
        soma = sum(int(cpf[i]) * ((digit_pos + 1) - i) for i in range(digit_pos))
        resto = (soma * 10) % 11
        if resto == 10:
            resto = 0
        if resto != int(cpf[digit_pos]):
            return False

    return True
