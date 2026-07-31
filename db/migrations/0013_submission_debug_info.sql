-- CORRADI-BOT · guarda el texto y el motivo en los envíos que NO llegan a publicarse
--
-- Hasta ahora `submissions` solo registraba el status (created | duplicate | not_opportunity |
-- rate_limited | error | ...), nunca el texto que mandó la persona ni por qué se rechazó. Para
-- lo que SÍ se publica, el texto sobrevive en projects.raw_message -- pero para lo rechazado
-- (el caso real que hizo saltar la falta: un usuario se bloqueó por spam_auto sin dejar rastro
-- de qué había mandado) no había forma de investigar después. Estas dos columnas son nullable
-- a propósito: solo se rellenan en los estados donde no existe ya un `projects` con el texto.

ALTER TABLE submissions ADD COLUMN IF NOT EXISTS raw_text TEXT;
ALTER TABLE submissions ADD COLUMN IF NOT EXISTS reason TEXT;
