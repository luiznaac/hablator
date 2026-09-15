# Hablator — hub de notificações

Hub de notificações do homelab: recebe pedidos de envio de outros projetos e os entrega por canais, registrando o histórico de cada tentativa de entrega.

## Language

### Envio

**Notification**:
O pedido de notificação: um por requisição, com conteúdo base (subject/body) e `source` opcional. Gera uma Delivery por canal escolhido; seu status (`succeeded`/`failed`/`pending`) é derivado das deliveries, não persistido.
_Avoid_: mensagem, message, alerta.

**Delivery**:
A intenção de entregar uma Notification por um canal, com destinatários, conteúdo resolvido e opções do canal. Tem status e ciclo de vida próprios (`pending`, `in_progress`, `succeeded`, `failed`).
_Avoid_: envio, job, task.

**Attempt**:
Uma execução de uma Delivery contra um provider, registrada de forma append-only com número sequencial, resultado, erro e classificação de retriabilidade. Uma Delivery pode ter várias.
_Avoid_: tentativa, try.

**Content**:
O conteúdo efetivamente enviado por uma Delivery: o override específico do canal ou uma cópia do conteúdo base da Notification no momento do envio.
_Avoid_: body, payload, template.

**Recipient**:
Endereço de destino no vocabulário de um canal: lista de endereços de email no email, exatamente um tópico no push.
_Avoid_: destinatário, target, address.

**Source**:
Origem opcional da Notification — o projeto ou consumidor que pediu o envio (ex.: `valoab`).
_Avoid_: origin, caller.

### Canais e falhas

**Channel**:
O meio de entrega: `email`, `push`, `sms` ou `voice`. Só email e push têm provider configurado nesta fase; sms e voice existem apenas no vocabulário.
_Avoid_: meio, transporte.

**Provider**:
A implementação concreta de um canal que executa uma tentativa (ex.: Mailgun no email, ntfy no push). Fica registrado no Attempt.
_Avoid_: gateway, driver.

**Retriable**:
Classificação de um Attempt falho que pode gerar nova tentativa (timeout, erro de rede, 5xx, 429). Falha não retriable encerra a Delivery.
_Avoid_: transient, recoverable, retryable.
