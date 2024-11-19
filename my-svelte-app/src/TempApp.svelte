<script>
    import { onMount, afterUpdate } from 'svelte';
    import SvelteMarkdown from 'svelte-markdown';

    let messages = [];
    let inputMessage = '';
    let socket;
    let messagesEnd;
    let textareaElement;
    let messageContainer;
    let isUserScrolled = false;
    let isBotResponding = false;
    let botResponseTimeout;
    let shouldIgnoreIncomingMessages = false;

    onMount(() => {
        socket = new WebSocket('ws://localhost:8000/ws');

        socket.onopen = () => {
            console.log('WebSocket connection established');
        };

        socket.onmessage = (event) => {
            if (shouldIgnoreIncomingMessages) {
                return;
            }
            const chunk = event.data;
            isBotResponding = true;

            if (
                messages.length === 0 ||
                messages[messages.length - 1].from !== 'bot' ||
                shouldIgnoreIncomingMessages
            ) {
                messages = [...messages, { from: 'bot', text: chunk }];
            } else {
                messages = messages.slice(0, -1).concat({
                    from: 'bot',
                    text: messages[messages.length - 1].text + chunk,
                });
            }

            if (botResponseTimeout) {
                clearTimeout(botResponseTimeout);
            }

            botResponseTimeout = setTimeout(() => {
                isBotResponding = false;
            }, 250);
        };

        socket.onclose = () => {
            console.log('WebSocket connection closed');
            isBotResponding = false;
        };

        messageContainer.addEventListener('scroll', () => {
            const { scrollTop, scrollHeight, clientHeight } = messageContainer;
            isUserScrolled = Math.abs(scrollHeight - clientHeight - scrollTop) > 10;
        });

        if (textareaElement) {
            textareaElement.style.height = '36px';
        }
    });

    afterUpdate(() => {
        if (!isUserScrolled) {
            messagesEnd.scrollIntoView({ behavior: 'smooth' });
        }
    });

    function sendMessage() {
        if (inputMessage.trim() !== '' && !isBotResponding) {
            messages = [...messages, { from: 'user', text: inputMessage }];
            socket.send(inputMessage);
            inputMessage = '';
            if (textareaElement) {
                textareaElement.style.height = '36px';
            }
            isUserScrolled = false;
            shouldIgnoreIncomingMessages = false;
        }
    }

    function stopBotResponse() {
        if (isBotResponding) {
            socket.send('__STOP__');
            isBotResponding = false;
            shouldIgnoreIncomingMessages = true;
            if (botResponseTimeout) {
                clearTimeout(botResponseTimeout);
            }
            messages = [...messages];
        }
    }

    function handleButtonClick() {
        if (isBotResponding) {
            stopBotResponse();
        } else {
            sendMessage();
        }
    }

    function handleKeyDown(event) {
        if (event.key === 'Enter' && !event.shiftKey) {
            event.preventDefault();
            sendMessage();
        }
    }

    function adjustTextareaHeight() {
        if (textareaElement) {
            textareaElement.style.height = '36px';
            const newHeight = Math.max(36, Math.min(textareaElement.scrollHeight, 100));
            textareaElement.style.height = newHeight + 'px';
        }
    }
</script>

<div class="app">
    <div class="header">
        <div class="header-title">llm_chatbot</div>
    </div>
    <div class="chat-container">
        <div class="messages" bind:this={messageContainer}>
            {#each messages as message}
                <div class="message {message.from}">
                    {#if message.from === 'bot'}
                        <div class="avatar">
                            <svg width="24" height="24" viewBox="0 0 24 24" fill="#FFFFFF">
                                <circle cx="12" cy="12" r="10" />
                                <rect x="9" y="9" width="6" height="6" fill="#121212" />
                            </svg>
                        </div>
                    {/if}
                   <div class="text">
                        {#if message.from === 'bot'}
                            <SvelteMarkdown source={message.text} />
                        {:else}
                            {message.text}
                        {/if}
                    </div>
                </div>
            {/each}
            <div bind:this={messagesEnd}></div>
        </div>
        <div class="input-wrapper">
            <div class="input-container">
                <textarea
                    bind:this={textareaElement}
                    bind:value={inputMessage}
                    placeholder="Type a message..."
                    on:keydown={handleKeyDown}
                    on:input={adjustTextareaHeight}
                ></textarea>
                <button
                    class="send-button"
                    on:click={handleButtonClick}
                    disabled={!inputMessage.trim() && !isBotResponding}
                >
                    {#if isBotResponding}
                        <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor">
                            <circle cx="12" cy="12" r="10" stroke="none" />
                            <rect x="9" y="9" width="6" height="6" fill="#FFFFFF" />
                        </svg>
                    {:else}
                        <svg
                            width="20"
                            height="20"
                            viewBox="0 0 24 24"
                            fill="none"
                            stroke="currentColor"
                            stroke-width="2"
                            stroke-linecap="round"
                            stroke-linejoin="round"
                        >
                            <line x1="12" y1="19" x2="12" y2="5" />
                            <polyline points="5 12 12 5 19 12" />
                        </svg>
                    {/if}
                </button>
            </div>
        </div>
    </div>
</div>

<style>
  .text {
    background-color: #0d0d0d;
    color: #e0e0e0;
  }

  /*Table Styles */
  :global(.text table) {
    width: 100%;
    border-collapse: separate;
    border-spacing: 0;
    margin-top: 1rem;
    margin-bottom: 1rem;
    border: 1px solid #333;
    border-radius: 10px;
    overflow: hidden;
  }

  :global(.text th),
  :global(.text td) {
    border: 1px solid #333;
    padding: 12px 15px;
    text-align: left;
    color: #cccccc;
  }

  :global(.text th) {
    background-color: #2b2b2b;
    color: #ffffff;
    font-weight: bold;
  }

  :global(.text tr:nth-child(even)) {
    background-color: #1a1a1a;
  }

  :global(.text tr:hover) {
    background-color: #333333;
  }
  :global(.text pre),
  :global(.text pre code),
  :global(.text code) {
      display: block;
      padding: 1em;
      background-color: #1E1E1E;
      color: #FFFFFF;
      border-radius: 4px;
      white-space: pre-wrap;
      word-break: break-word;
      overflow-wrap: anywhere;
      overflow-x: hidden;
      max-width: 100%;
  }
</style>



