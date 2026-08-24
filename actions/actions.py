from typing import Any, Text, Dict, List
from rasa_sdk import Action, Tracker, ValidationAction
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.events import SlotSet
from rasa_sdk.types import DomainDict
import pandas as pd
import os
import unicodedata

# Acción personalizada para manejar respuestas que no fueron entendidas
class ActionDefaultFallback(Action):
    def name(self) -> Text:
        return "action_default_fallback"

    async def run(
        self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]
    ) -> List[Dict[Text, Any]]:
        
        # Envia un mensaje genérico cuando el bot no entiende
        dispatcher.utter_message(response="utter_default")
        
        return []

# Acción para validar que el número de personas sea un valor correcto
class ActionValidateNumeroPersonas(Action):

    def name(self) -> Text:
        return "action_validate_numero_personas"

    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        
        numero_personas_str = tracker.get_slot("numero_personas")
        
         # Convierte el número a entero (admite flotantes escritos por error)
        try:
            numero_personas = int(float(numero_personas_str))
             # Verifica que el número sea mayor que cero
            if numero_personas <= 0:
                dispatcher.utter_message(text="Por favor, ingresa un número válido de personas.")
                return [SlotSet("numero_personas", None)]
            else:
                return [SlotSet("numero_personas", numero_personas)]
        # Error si el valor ingresado no es numérico        
        except (ValueError, TypeError):
            dispatcher.utter_message(text="Por favor, ingresa un número válido de personas.")
            return [SlotSet("numero_personas", None)]

# Acción principal que gestiona la confirmación o sugerencia de reservas
class ActionConfirmarReserva(Action):

    def name(self) -> Text:
        return "action_confirmar_reserva"

    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:

        # Obtiene valores de los slots y normaliza el día
        numero_personas = tracker.get_slot('numero_personas')
        fecha_reserva = normalize_day(tracker.get_slot('fecha_reserva'))
        hora_reserva = tracker.get_slot('hora_reserva')
        hora_sugerida = tracker.get_slot('hora_reserva_sugerida')
        nombre_cliente = tracker.get_slot('nombre_cliente')
        telefono_cliente = tracker.get_slot('telefono_cliente')
        needs_confirmation = tracker.get_slot("needs_confirmation")

        file_path = os.path.join(
            os.path.dirname(__file__),
            "restaurant_availability.xlsx"
        )

        # Verifica si el archivo de disponibilidad existe
        if not os.path.exists(file_path):
            dispatcher.utter_message(text="El archivo de reservas no existe en la ruta especificada.")
            return []

        try:
            df = pd.read_excel(file_path)

             # Si el usuario está confirmando una hora sugerida
            if needs_confirmation and hora_sugerida:
                mensaje_confirmacion = (
                    f"Perfecto, {nombre_cliente}. He confirmado tu reserva para {numero_personas} personas "
                    f"el {fecha_reserva} a las {hora_sugerida}. Te contactaremos al {telefono_cliente} "
                    f"si necesitamos confirmar algo. ¡Te esperamos en La Tentación de Madrid!"
                )
                dispatcher.utter_message(text=mensaje_confirmacion)
                return [
                    SlotSet("hora_reserva", hora_sugerida),
                    SlotSet("fecha_reserva", fecha_reserva),  # Overwrite fecha_reserva
                    SlotSet("hora_reserva_sugerida", None),
                    SlotSet("needs_confirmation", None)
                ]

            # Busca disponibilidad exacta para día, hora y capacidad
            matching_slot = df[
                (df['Day'] == fecha_reserva) &
                (df['Time Slot'] == hora_reserva) &
                (df['Seats'] >= numero_personas)
            ]

             #Verifica si al menos una mesa está disponible
            if not matching_slot.empty and any(matching_slot['Status'] == "Available"):
                mensaje_confirmacion = (
                    f"Perfecto, {nombre_cliente}. He confirmado tu reserva para {numero_personas} personas "
                    f"el {fecha_reserva} a las {hora_reserva}. Te contactaremos al {telefono_cliente} "
                    f"si necesitamos confirmar algo. ¡Te esperamos en La Tentación de Madrid!"
                )
                dispatcher.utter_message(text=mensaje_confirmacion)
                return [
                    SlotSet("fecha_reserva", fecha_reserva),
                    SlotSet("hora_reserva", hora_reserva)
                ]

            # Si no hay disponibilidad, buscar otros horarios ese mismo día
            day_slots = df[df['Day'] == fecha_reserva]
            available_alternatives = day_slots[
                (day_slots['Seats'] >= numero_personas) &
                (day_slots['Status'] == "Available")
            ]
            # Sugiere la primera hora disponible del mismo día
            if not available_alternatives.empty:
                closest_available_time = available_alternatives.iloc[0]['Time Slot']
                mensaje_alternativo = (
                    f"Perdón, no tenemos lugar a esa hora. Te puedo ofrecer {closest_available_time}. ¿Te parece bien?"
                )
                dispatcher.utter_message(text=mensaje_alternativo)
                return [
                    SlotSet("hora_reserva_sugerida", closest_available_time),
                    SlotSet("needs_confirmation", True)
                ]
            else:
                # Si no hay disponibilidad ese día, buscar el mismo horario en otro día
                same_time_other_days = df[
                    (df['Time Slot'] == hora_reserva) &
                    (df['Seats'] >= numero_personas) &
                    (df['Status'] == "Available") &
                    (df['Day'] != fecha_reserva)
                ]

                # Sugiere otro día con el mismo horario
                if not same_time_other_days.empty:
                    alternative_day = same_time_other_days.iloc[0]['Day']
                    mensaje_otro_dia = (
                        f"Perdón, no tenemos lugar en este día. Pero sí puedo ofrecerte el mismo horario ({hora_reserva}) el {alternative_day}. ¿Te gustaría reservar para ese día?"
                    )
                    dispatcher.utter_message(text=mensaje_otro_dia)
                    return [
                        SlotSet("hora_reserva_sugerida", hora_reserva),
                        SlotSet("fecha_reserva", alternative_day),
                        SlotSet("needs_confirmation", True)
                    ]
                    # No hay disponibilidad en ningún día ni horario
                else:
                    dispatcher.utter_message(text="Perdón, no tenemos lugar ni en este día ni en el mismo horario en otros días.")
                    return []
         # Error al procesar el archivo
        except Exception as e:
            dispatcher.utter_message(text="Error al verificar disponibilidad.")
            print(f"Error leyendo archivo de Excel: {e}")
    
        return []

# Función para normalizar nombres de días (quita acentos y pasa a minúsculas)
def normalize_day(day: str) -> str:
    if not day:
        return ""

    # Convierte todo a minúsculas
    day = day.lower()

    # Elimina tildes y acentos usando Unicode
    day = ''.join(
        c for c in unicodedata.normalize('NFD', day)
        if unicodedata.category(c) != 'Mn'
    )

    return day