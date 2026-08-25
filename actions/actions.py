from typing import Any, Text, Dict, List
from rasa_sdk import Action, Tracker
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.events import SlotSet
import pandas as pd
import os
import unicodedata
import re


# Acción personalizada para manejar respuestas que no fueron entendidas
class ActionDefaultFallback(Action):

    def name(self) -> Text:
        return "action_default_fallback"

    async def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any]
    ) -> List[Dict[Text, Any]]:

        dispatcher.utter_message(response="utter_default")
        return []


# Acción para validar que el número de personas sea correcto
class ActionValidateNumeroPersonas(Action):

    def name(self) -> Text:
        return "action_validate_numero_personas"

    async def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any]
    ) -> List[Dict[Text, Any]]:

        numero_personas_str = tracker.get_slot("numero_personas")

        try:
            numero_personas = int(float(numero_personas_str))

            if numero_personas <= 0:
                dispatcher.utter_message(
                    text="Por favor, ingresa un número válido de personas."
                )
                return [SlotSet("numero_personas", None)]

            return [SlotSet("numero_personas", numero_personas)]

        except (ValueError, TypeError):
            dispatcher.utter_message(
                text="Por favor, ingresa un número válido de personas."
            )
            return [SlotSet("numero_personas", None)]


# Acción principal para confirmar o sugerir reservas
class ActionConfirmarReserva(Action):

    def name(self) -> Text:
        return "action_confirmar_reserva"

    def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any]
    ) -> List[Dict[Text, Any]]:

        # Obtener slots
        numero_personas = tracker.get_slot("numero_personas")
        fecha_reserva = normalize_day(tracker.get_slot("fecha_reserva"))
        hora_reserva = normalize_time(tracker.get_slot("hora_reserva"))
        hora_sugerida = tracker.get_slot("hora_reserva_sugerida")
        nombre_cliente = tracker.get_slot("nombre_cliente")
        telefono_cliente = tracker.get_slot("telefono_cliente")
        needs_confirmation = tracker.get_slot("needs_confirmation")

        # Convertir número de personas a entero
        try:
            numero_personas = int(float(numero_personas))
        except (ValueError, TypeError):
            dispatcher.utter_message(
                text="No pude interpretar el número de personas."
            )
            return [SlotSet("numero_personas", None)]

        # Buscar el Excel en la misma carpeta que actions.py
        file_path = os.path.join(
            os.path.dirname(__file__),
            "restaurant_availability.xlsx"
        )

        if not os.path.exists(file_path):
            dispatcher.utter_message(
                text="El archivo de reservas no existe."
            )
            print("ARCHIVO NO ENCONTRADO:", file_path)
            return []

        try:
            df = pd.read_excel(file_path)

            # Normalizar los datos del Excel
            df["Day"] = df["Day"].apply(normalize_day)
            df["Time Slot"] = df["Time Slot"].apply(normalize_time)
            df["Status"] = df["Status"].astype(str).str.strip()
            df["Seats"] = pd.to_numeric(df["Seats"], errors="coerce")
            df["Customer Name"] = df["Customer Name"].astype("string")
            df["Customer Phone"] = df["Customer Phone"].astype("string")


            # Si el usuario está confirmando una hora sugerida
            if needs_confirmation and hora_sugerida:

                # Buscar una mesa disponible para la hora alternativa
                suggested_slot = df[
                    (df["Day"] == fecha_reserva)
                    & (df["Time Slot"] == hora_sugerida)
                    & (df["Seats"] >= numero_personas)
                    & (df["Status"] == "Available")
                ]

                if suggested_slot.empty:
                    dispatcher.utter_message(
                        text=(
                            "Lo siento, esa hora acaba de quedarse sin disponibilidad. "
                            "Podemos buscar otra opción."
                        )
                    )

                    return [
                        SlotSet("hora_reserva_sugerida", None),
                        SlotSet("needs_confirmation", None)
                    ]

                # Elegir la mesa más pequeña adecuada
                best_table = suggested_slot.sort_values("Seats").iloc[0]
                table_index = best_table.name

                # Guardar los datos de la reserva
                df.loc[table_index, "Status"] = "Booked"
                df.loc[table_index, "Party Size"] = numero_personas
                df.loc[table_index, "Customer Name"] = nombre_cliente
                df.loc[table_index, "Customer Phone"] = telefono_cliente

                # Guardar los cambios
                df.to_excel(file_path, index=False)


                mensaje_confirmacion = (
                    f"Perfecto, {nombre_cliente}. He confirmado tu reserva "
                    f"para {numero_personas} personas el {fecha_reserva} "
                    f"a las {hora_sugerida}. Te contactaremos al "
                    f"{telefono_cliente} si necesitamos confirmar algo. "
                    f"¡Te esperamos en La Tentación de Madrid!"
                )

                dispatcher.utter_message(text=mensaje_confirmacion)

                return [
                    SlotSet("hora_reserva", hora_sugerida),
                    SlotSet("fecha_reserva", fecha_reserva),
                    SlotSet("hora_reserva_sugerida", None),
                    SlotSet("needs_confirmation", None)
                ]

            # Buscar una mesa para el número solicitado O MÁS
            matching_slot = df[
                (df["Day"] == fecha_reserva)
                & (df["Time Slot"] == hora_reserva)
                & (df["Seats"] >= numero_personas)
                & (df["Status"] == "Available")
            ]

            # Hay disponibilidad exacta
            if not matching_slot.empty:

                # Elegir la mesa disponible más pequeña
                # que pueda acomodar al grupo
                best_table = matching_slot.sort_values("Seats").iloc[0]
                table_index = best_table.name

                # Guardar los datos de la reserva
                df.loc[table_index, "Status"] = "Booked"
                df.loc[table_index, "Party Size"] = numero_personas
                df.loc[table_index, "Customer Name"] = nombre_cliente
                df.loc[table_index, "Customer Phone"] = telefono_cliente

                # Guardar los cambios en Excel
                df.to_excel(file_path, index=False)


                mensaje_confirmacion = (
                    f"Perfecto, {nombre_cliente}. He confirmado tu reserva "
                    f"para {numero_personas} personas el {fecha_reserva} "
                    f"a las {hora_reserva}. Te contactaremos al "
                    f"{telefono_cliente} si necesitamos confirmar algo. "
                    f"¡Te esperamos en La Tentación de Madrid!"
                )

                dispatcher.utter_message(text=mensaje_confirmacion)

                return [
                    SlotSet("fecha_reserva", fecha_reserva),
                    SlotSet("hora_reserva", hora_reserva)
                ]

            # No hay mesa a esa hora:
            # buscar otras horas disponibles ese mismo día
            available_alternatives = df[
                (df["Day"] == fecha_reserva)
                & (df["Seats"] >= numero_personas)
                & (df["Status"] == "Available")
            ].copy()

            if not available_alternatives.empty:

                # Convertir horarios para poder calcular cuál es el más cercano
                requested_time = pd.to_datetime(
                    hora_reserva,
                    format="%I:%M %p"
                )

                available_alternatives["parsed_time"] = pd.to_datetime(
                    available_alternatives["Time Slot"],
                    format="%I:%M %p"
                )

                available_alternatives["time_difference"] = (
                    available_alternatives["parsed_time"] - requested_time
                ).abs()

                closest_row = available_alternatives.loc[
                    available_alternatives["time_difference"].idxmin()
                ]

                closest_available_time = closest_row["Time Slot"]

                mensaje_alternativo = (
                    f"Perdón, no tenemos lugar a las {hora_reserva}. "
                    f"La hora disponible más cercana es {closest_available_time}."
                )

                dispatcher.utter_message(text=mensaje_alternativo)

                return [
                    SlotSet(
                        "hora_reserva_sugerida",
                        closest_available_time
                    ),
                    SlotSet("needs_confirmation", True)
                ]

            # Si no hay ninguna mesa ese día,
            # buscar el mismo horario otro día
            same_time_other_days = df[
                (df["Time Slot"] == hora_reserva)
                & (df["Seats"] >= numero_personas)
                & (df["Status"] == "Available")
                & (df["Day"] != fecha_reserva)
            ]

            if not same_time_other_days.empty:
                alternative_day = same_time_other_days.iloc[0]["Day"]

                mensaje_otro_dia = (
                    f"Perdón, no tenemos lugar ese día. "
                    f"Pero puedo ofrecerte las {hora_reserva} "
                    f"el {alternative_day}. "
                    f"¿Te gustaría reservar para ese día?"
                )

                dispatcher.utter_message(text=mensaje_otro_dia)

                return [
                    SlotSet(
                        "hora_reserva_sugerida",
                        hora_reserva
                    ),
                    SlotSet(
                        "fecha_reserva",
                        alternative_day
                    ),
                    SlotSet(
                        "needs_confirmation",
                        True
                    )
                ]

            dispatcher.utter_message(
                text=(
                    "Perdón, no tenemos disponibilidad para "
                    "ese tamaño de grupo."
                )
            )

        except Exception as e:
            dispatcher.utter_message(
                text="Error al verificar disponibilidad."
            )
            print("ERROR LEYENDO EXCEL:", repr(e))

        return []


# Normalizar nombres de días
def normalize_day(day: str) -> str:

    if not day:
        return ""

    day = str(day).lower().strip()

    day = "".join(
        c
        for c in unicodedata.normalize("NFD", day)
        if unicodedata.category(c) != "Mn"
    )

    return day

def normalize_time(time_value: str) -> str:
    if not time_value:
        return ""

    text = str(time_value).strip().lower()

    # Quitar expresiones frecuentes
    text = text.replace("a las", "").strip()

    # Caso 1: el usuario especifica AM o PM
    # Ejemplos: "10:00 PM", "10 PM"
    match = re.search(
        r"(\d{1,2})(?::(\d{2}))?\s*(am|pm)",
        text,
        re.IGNORECASE
    )

    if match:
        hour = int(match.group(1))
        minute = match.group(2) or "00"
        period = match.group(3).upper()

        return f"{hour:02d}:{minute} {period}"

    # Caso 2: hora sin AM/PM
    # Ejemplos: "10:00", "10", "22:00"
    match = re.search(
        r"^(\d{1,2})(?::(\d{2}))?$",
        text
    )

    if match:
        hour = int(match.group(1))
        minute = match.group(2) or "00"

        # Formato 24 horas: 18:00-23:59
        if 18 <= hour <= 23:
            hour_12 = hour - 12
            return f"{hour_12:02d}:{minute} PM"

        # Medianoche
        if hour == 0 or hour == 24:
            return f"12:{minute} AM"

        # Debido al horario del restaurante,
        # 6-11 se interpreta como PM
        if 6 <= hour <= 11:
            return f"{hour:02d}:{minute} PM"

        # 12:00 se interpreta como medianoche
        if hour == 12:
            return f"12:{minute} AM"

    return text

class ActionNormalizeHora(Action):

    # Nombre con el que Rasa identifica esta acción.
    # Este mismo nombre debe usarse cuando llamas a la acción desde el flow/domain.
    def name(self) -> Text:
        return "action_normalize_hora"

    # Método que Rasa ejecuta cuando se llama a esta acción.
    def run(
        self,
        dispatcher: CollectingDispatcher,  # Permite enviar mensajes al usuario.
        tracker: Tracker,                  # Contiene el estado actual de la conversación y los slots.
        domain: Dict[Text, Any]            # Contiene información del dominio de Rasa.
    ) -> List[Dict[Text, Any]]:

        # Obtiene del slot "hora_reserva" la hora introducida por el usuario.
        # Por ejemplo: "10 de la noche", "22:00", "10 pm", etc.
        hora_original = tracker.get_slot("hora_reserva")

        # Envía la hora original a nuestra función normalize_time().
        # Esta función transforma la hora a un formato estándar.
        hora_normalizada = normalize_time(hora_original)

        # Actualiza el slot "hora_reserva" con la hora ya normalizada.
        # Así, el resto del chatbot trabaja siempre con el mismo formato.
        return [SlotSet("hora_reserva", hora_normalizada)]

class ActionValidateTelefonoCliente(Action):

    # Nombre con el que Rasa identifica esta acción personalizada.
    def name(self) -> Text:
        return "action_validate_telefono_cliente"

    # Método que Rasa ejecuta cuando se llama a esta acción.
    # Es async porque puede ejecutarse de forma asíncrona dentro de Rasa.
    async def run(
        self,
        dispatcher: CollectingDispatcher,  # Permite enviar mensajes al usuario.
        tracker: Tracker,                  # Contiene los slots y el estado de la conversación.
        domain: Dict[Text, Any]            # Contiene la configuración del dominio de Rasa.
    ) -> List[Dict[Text, Any]]:

        # Recuperamos el teléfono que Rasa tiene guardado
        # en el slot "telefono_cliente".
        telefono = tracker.get_slot("telefono_cliente")

        # Si el slot está vacío, es None o no contiene ningún valor,
        # informamos al usuario de que debe introducir un teléfono válido.
        if not telefono:
            dispatcher.utter_message(
                text="Por favor, introduce un número de teléfono válido."
            )

            # Borramos cualquier valor incorrecto del teléfono
            # y marcamos el teléfono como no válido.
            return [
                SlotSet("telefono_cliente", None),
                SlotSet("telefono_valido", False)
            ]

        # Convertimos el teléfono a texto por seguridad.
        # strip() elimina espacios al principio y al final.
        telefono = str(telefono).strip()

        # Eliminamos todo lo que NO sea un dígito.
        # \D significa "cualquier carácter que no sea un número".
        #
        # Por ejemplo:
        # "+34 612-345-678" -> "34612345678"
        digitos = re.sub(r"\D", "", telefono)

        # Consideramos válido un teléfono que tenga
        # entre 7 y 15 dígitos.
        if 7 <= len(digitos) <= 15:

            # Creamos una versión limpia del teléfono.
            #
            # Si el usuario escribió el teléfono empezando por "+",
            # conservamos ese símbolo.
            #
            # Ejemplo:
            # "+34 612 345 678" -> "+34612345678"
            #
            # Si no tenía "+", guardamos únicamente los números.
            # "612 345 678" -> "612345678"
            telefono_normalizado = (
                f"+{digitos}"
                if telefono.startswith("+")
                else digitos
            )

            # Guardamos el teléfono normalizado
            # y marcamos que la validación fue correcta.
            return [
                SlotSet("telefono_cliente", telefono_normalizado),
                SlotSet("telefono_valido", True)
            ]

        # Eliminamos el teléfono incorrecto para que Rasa
        # pueda solicitarlo nuevamente y marcamos la validación como fallida.
        return [
            SlotSet("telefono_cliente", None),
            SlotSet("telefono_valido", False)
        ]