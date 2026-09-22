# Claude API Fundamentals

Core concepts for building against the Claude API (the Messages API),
covering authentication, request structure, streaming, and error handling.

## Overview

The Messages API is the primary way to send conversation turns to a Claude
model and get a completion back. A request is a list of messages (each
with a `role` of `user` or `assistant`) plus a `model` name and a
`max_tokens` limit; the response contains the assistant's reply along with
usage and stop-reason metadata.

## Messages API Basics

Every request needs, at minimum: the target model, a `max_tokens` value,
and a non-empty `messages` array. An optional top-level `system` parameter
sets the system prompt — instructions that shape the assistant's behavior
for the whole conversation — separately from the conversation turns
themselves, rather than as a fake first message.

Multi-turn conversations are stateless on the API side: the caller resends
the full message history with every request. There is no server-side
session to reference by ID; the client is the source of truth for
conversation state.

## Authentication and Rate Limits

Requests are authenticated with an API key sent in a header, not embedded
in the request body or URL. Keys should never be shipped to a browser or
mobile client — API calls belong behind a server-side component that holds
the key.

Rate limits apply per organization and are expressed as both a requests
count and a tokens count over a rolling time window. When a request is
rate-limited, the API returns a 429 response with headers indicating how
long to wait before retrying; a well-behaved client backs off rather than
retrying immediately in a tight loop.

## Streaming Responses

Setting `stream: true` on a request changes the response from a single
JSON payload to a sequence of server-sent events, so the caller can render
tokens as they arrive instead of waiting for the full completion. This
matters most for long-form generation where waiting for the complete
response would make the UI feel unresponsive.

Streamed events include incremental content deltas as well as lifecycle
events (message start, content block start/stop, message stop) that let
the client track state — for example, knowing when one content block ends
and another begins, which matters when a response mixes text with tool
calls.

## Error Handling

API errors are returned with an HTTP status code and a JSON body
describing the error type. The categories that matter most in practice:
`400` for a malformed request (fix the request), `401` for an invalid or
missing API key (fix the credential), `429` for rate limiting (back off
and retry), and `5xx` for a transient server-side issue (retry with
backoff).

A production integration should distinguish these categories rather than
treating every non-200 response the same way — retrying a 400 in a loop
will never succeed, while not retrying a 429 or 5xx wastes a recoverable
request.
