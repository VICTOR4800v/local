import json
from google import genai
from google.genai import types
from google.genai import errors as genai_errors
from ai.prompts import SYSTEM_PROMPT, TOOLS_SCHEMA
from ai.usage import UsageTracker

MAX_TOOL_ITERATIONS = 5  # limite di sicurezza per evitare loop infiniti di tool-calling

# gemini-2.5-flash-lite ha una quota giornaliera gratuita molto più alta di
# gemini-2.5-flash, a fronte di un ragionamento leggermente più semplice:
# per un assistente con tool-calling è il compromesso giusto.
MODEL_NAME = "gemini-flash-lite-latest"


def _to_gemini_tools(openai_style_schema):
    """
    ai/prompts.py definisce i tool in stile OpenAI/Groq
    (es. {"type": "function", "function": {"name": ..., "parameters": ...}}).
    Gemini vuole gli stessi identici campi (name/description/parameters),
    solo incapsulati in un types.FunctionDeclaration: li convertiamo qui
    così prompts.py resta invariato e riusabile con qualunque provider.
    """
    declarations = []
    for entry in openai_style_schema:
        fn = entry["function"]
        declarations.append(
            types.FunctionDeclaration(
                name=fn["name"],
                description=fn.get("description", ""),
                parameters=fn.get("parameters", {"type": "object", "properties": {}}),
            )
        )
    return [types.Tool(function_declarations=declarations)]


class JarvisAI:
    def __init__(self, api_key, tool_manager):
        self.client = genai.Client(api_key=api_key)
        self.tool_manager = tool_manager
        self.gemini_tools = _to_gemini_tools(TOOLS_SCHEMA)

        # A differenza di Groq/OpenAI, Gemini gestisce la cronologia come
        # lista di Content (role="user"/"model"), non come dict "messages".
        self.history = []

        # Contatore locale di richieste/token per monitorare il consumo
        # della quota gratuita di Google AI Studio (puramente informativo).
        self.usage = UsageTracker()

    async def process_command(self, user_text):
        self.history.append(
            types.Content(role="user", parts=[types.Part(text=user_text)])
        )
        tool_used = False

        for _ in range(MAX_TOOL_ITERATIONS):
            try:
                response = self.client.models.generate_content(
                    model=MODEL_NAME,
                    contents=self.history,
                    config=types.GenerateContentConfig(
                        system_instruction=SYSTEM_PROMPT,
                        tools=self.gemini_tools,
                    ),
                )
            except genai_errors.ClientError as e:
                # Tolgo dalla history l'ultimo messaggio utente: la richiesta
                # non è mai stata processata dal modello, non deve restare
                # "appesa" nella conversazione.
                self.history.pop()
                if getattr(e, "code", None) == 429 or "RESOURCE_EXHAUSTED" in str(e):
                    print(f"[Gemini] Rate limit raggiunto: {e}")
                    return (
                        "Ho esaurito la quota gratuita di richieste a Gemini per il momento. "
                        "Riprova tra un minuto o più tardi.",
                        tool_used,
                    )
                print(f"[Gemini] Errore API: {e}")
                return "Ho avuto un problema nel contattare l'IA, riprova.", tool_used
            except Exception as e:
                # Qualunque altro errore imprevisto (timeout di rete, risposta
                # malformata, ecc.): NON deve mai risalire fino a engine.py,
                # altrimenti l'intero loop di elaborazione comandi si blocca
                # e la GUI resta incastrata su "thinking" per sempre.
                self.history.pop()
                print(f"[Gemini] Errore imprevisto: {e}")
                return "Ho avuto un problema interno imprevisto, riprova.", tool_used

            # Traccio il consumo di token per questa richiesta, a prescindere
            # da cosa contenga la risposta (utile per il monitor in GUI).
            self.usage.add(getattr(response, "usage_metadata", None))

            if not response.candidates:
                self.history.pop()
                return "Non ho ricevuto una risposta valida dall'IA, riprova.", tool_used

            candidate = response.candidates[0]

            if candidate.content is None or not candidate.content.parts:
                # Successo capita ad esempio se la risposta è stata bloccata
                # dai filtri di sicurezza di Gemini o troncata per limite
                # token: senza questo controllo, l'accesso a
                # candidate.content.parts più sotto solleverebbe un
                # AttributeError non gestito.
                self.history.pop()
                reason = getattr(candidate, "finish_reason", "sconosciuto")
                print(f"[Gemini] Risposta senza contenuto utilizzabile (finish_reason={reason})")
                return (
                    "Non sono riuscito a generare una risposta utile (probabilmente bloccata "
                    "dai filtri di sicurezza o troppo lunga). Prova a riformulare la richiesta.",
                    tool_used,
                )

            # Salva la risposta del modello (role="model") nella cronologia
            self.history.append(candidate.content)

            function_calls = [
                part.function_call for part in candidate.content.parts if part.function_call
            ]

            if not function_calls:
                try:
                    return response.text, tool_used
                except Exception as e:
                    print(f"[Gemini] Errore nel leggere il testo della risposta: {e}")
                    return "Ho ricevuto una risposta in un formato inatteso, riprova.", tool_used

            tool_used = True
            response_parts = []
            for fc in function_calls:
                function_name = fc.name
                function_args = dict(fc.args) if fc.args else {}

                # Esegui il vero codice Python sul PC
                print(f"Esecuzione Tool: {function_name} con args: {function_args}")
                result = self.tool_manager.execute(function_name, function_args)

                response_parts.append(
                    types.Part.from_function_response(
                        name=function_name,
                        response={"result": str(result)},
                    )
                )

            # Il risultato del tool va rimandato come Content separato
            self.history.append(types.Content(role="user", parts=response_parts))

        # Se dopo troppi giri l'IA continua a voler chiamare tool, chiudiamo qui
        return "Ho eseguito diverse azioni ma non sono riuscito a formulare una risposta finale.", tool_used