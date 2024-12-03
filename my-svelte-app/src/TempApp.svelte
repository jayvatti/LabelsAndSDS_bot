<script>
    import {onMount, afterUpdate} from 'svelte';
    import SvelteMarkdown from 'svelte-markdown';
    import logo from '/src/static/assets/logo.png';
    import topLeftCrop from '/src/static/assets/topLeftCrop.png'; // Import the new image

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
                messages = [...messages, {from: 'bot', text: chunk}];
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
            const {scrollTop, scrollHeight, clientHeight} = messageContainer;
            isUserScrolled = Math.abs(scrollHeight - clientHeight - scrollTop) > 10;
        });

        if (textareaElement) {
            textareaElement.style.height = '36px';
        }
    });

    afterUpdate(() => {
        if (!isUserScrolled) {
            messagesEnd.scrollIntoView({behavior: 'smooth'});
        }
    });

    function sendMessage() {
        if (inputMessage.trim() !== '' && !isBotResponding) {
            messages = [...messages, {from: 'user', text: inputMessage}];
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
        <!-- Replace the header title text with the imported image -->
        <img src="{topLeftCrop}" alt="Top Left Crop" class="header-logo"/>
    </div>
    <div class="chat-container">
        <div class="messages" bind:this={messageContainer}>
            {#each messages as message}
                <div class="message {message.from}">
                    {#if message.from === 'bot'}
                        <div class="avatar">
                            <img src="{logo}" alt="Bot Avatar"/>
                        </div>
                    {/if}
                    <div class="text">
                        {#if message.from === 'bot'}
                            <SvelteMarkdown source={message.text}/>
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
                            <circle cx="12" cy="12" r="10" stroke="none"/>
                            <rect x="9" y="9" width="6" height="6" fill="#FFFFFF"/>
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
                            <line x1="12" y1="19" x2="12" y2="5"/>
                            <polyline points="5 12 12 5 19 12"/>
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

    /* Table Styles */
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

    /* Avatar Styles */
    .avatar {
        width: 27px; /* Consistent size */
        height: 27px; /* Consistent size */
        background-color: #ffffff; /* White background */
        border-radius: 50%; /* Circular crop */
        overflow: hidden; /* Ensure the image fits within the circle */
        display: flex;
        align-items: center;
        justify-content: center;
        margin-right: 10px; /* Consistent spacing */
        border: 3px solid #ffffff; /* Adds a 2px solid white border */
        flex-shrink: 0;
    }

    .avatar img {
        width: 100%;
        height: 100%;
        object-fit: cover; /* Ensures the image covers the container without distortion */
        transform: scale(1.0); /* Adjust scaling as needed */
    }

    /* Global Styles */
    :global(html, body) {
        margin: 0;
        padding: 0;
        height: 100%;
        width: 100%;
        background-color: #121212;
        color: #FFFFFF;
        font-family: 'Raleway', sans-serif;
        overflow: hidden;
    }

    body {
        background-color: #121212;
    }

    /*

    SCROLL BAR CODE
     */

    /* ----------------------------
     WebKit Browsers (Chrome, Safari, Opera)
     ---------------------------- */

    /* Messages Container Scrollbar */
    .messages::-webkit-scrollbar {
        width: 8px;
    }

    .messages::-webkit-scrollbar-track {
        background: transparent;
    }

    .messages::-webkit-scrollbar-thumb {
        background: rgba(255, 255, 255, 0); /* Fully transparent */
        border-radius: 4px;
        transition: background 0.3s;
    }

    .messages:hover::-webkit-scrollbar-thumb {
        background: rgba(255, 255, 255, 0.3); /* Visible on hover */
    }

    /* Textarea Scrollbar */
    .input-container textarea::-webkit-scrollbar {
        width: 8px;
    }

    .input-container textarea::-webkit-scrollbar-track {
        background: transparent;
    }

    .input-container textarea::-webkit-scrollbar-thumb {
        background: rgba(255, 255, 255, 0); /* Fully transparent */
        border-radius: 4px;
        transition: background 0.3s;
    }

    .input-container textarea:hover::-webkit-scrollbar-thumb {
        background: rgba(255, 255, 255, 0.3); /* Visible on hover */
    }

    /* ----------------------------
       Firefox
       ---------------------------- */

    /* Messages Container Scrollbar */
    .messages {
        scrollbar-width: thin; /* "auto" or "thin" */
        scrollbar-color: transparent transparent; /* thumb and track */
        transition: scrollbar-color 0.3s;
    }

    .messages:hover {
        scrollbar-color: rgba(255, 255, 255, 0.3) transparent; /* thumb on hover */
    }

    /* Textarea Scrollbar */
    .input-container textarea {
        scrollbar-width: thin; /* "auto" or "thin" */
        scrollbar-color: transparent transparent; /* thumb and track */
        transition: scrollbar-color 0.3s;
    }

    .input-container textarea:hover {
        scrollbar-color: rgba(255, 255, 255, 0.3) transparent; /* thumb on hover */
    }

    /* ----------------------------
       Internet Explorer and Edge
       ---------------------------- */

    /* These browsers have limited scrollbar styling capabilities.
       We'll keep the scrollbars minimal and consistent with the design. */

    .messages {
        -ms-overflow-style: -ms-autohiding-scrollbar; /* IE and Edge */
    }

    .input-container textarea {
        -ms-overflow-style: -ms-autohiding-scrollbar; /* IE and Edge */
    }


    /*

  SCROLL BAR CODE   ENDS
   */


    .app {
        height: 100%;
        position: relative;
    }

    .header {
        position: fixed;
        top: 0;
        width: 100%;
        height: 50px;
        background-color: #121212;
        z-index: 1;
        display: flex;
        align-items: center;
        padding-left: 20px;
    }

    .header-logo {
        height: 45px;
        width: auto;
        padding-left: 2px;
        padding-top: 20px;
    }

    .chat-container {
        display: flex;
        flex-direction: column;
        position: fixed;
        top: 50px;
        bottom: 0;
        width: 60vw;
        left: 50%;
        transform: translateX(-50%);
        overflow-y: hidden;
        overflow-x: hidden;
    }

    .messages {
        flex: 1;
        overflow-y: auto;
        overflow-x: hidden;
        padding: 20px;
        box-sizing: border-box;
    }

    .message {
        display: flex;
        margin-bottom: 20px;
        align-items: center;
        flex-wrap: nowrap;
    }

    .message.user {
        justify-content: flex-end;
    }

    .message.bot {
        justify-content: flex-start;
        align-items: flex-start;
    }

    .message.user .avatar {
        display: none;
    }

    .message .text {
        position: relative;
        line-height: 1.5;
        word-wrap: break-word;
        overflow-wrap: break-word;
        white-space: pre-wrap;
        max-width: 100%;
        overflow-x: hidden;
    }

    .message.user .text {
        background-color: #2C2C2C;
        color: #CCCCCC;
        text-align: left;
        border-radius: 15px;
        padding: 12px 20px;
        display: inline-block;
        max-width: 80%;
        margin-left: 0;
        margin-right: 10px;
    }

    .message.bot .text {
        background-color: transparent;
        color: #FFFFFF;
        padding: 0;
        margin-left: 10px;
        max-width: 100%;
        text-align: left;
        overflow-x: hidden;
        word-wrap: break-word;
        overflow-wrap: break-word;
    }

    /* Markdown Styling */
    :global(.text h1),
    :global(.text h2),
    :global(.text h3),
    :global(.text h4),
    :global(.text h5),
    :global(.text h6) {
        color: #FFFFFF;
        margin: 1em 0 0.5em;
    }

    :global(.text p) {
        margin: 0.5em 0;
        color: #FFFFFF;
    }

    :global(.text a) {
        color: #1E90FF;
        text-decoration: none;
    }

    :global(.text a:hover) {
        text-decoration: underline;
    }

    :global(.text ul),
    :global(.text ol) {
        margin: 0.5em 0 0.5em 1.5em;
    }

    :global(.text code) {
        background-color: #1E1E1E;
        color: #FFCB6B;
        padding: 2px 4px;
        border-radius: 4px;
        font-family: 'Raleway', sans-serif;
    }

    :global(.text pre),
    :global(.text pre code) {
        display: block;
        padding: 1em;
        background-color: #1E1E1E;
        color: #FFFFFF;
        border-radius: 4px;
        white-space: pre-wrap;
        word-wrap: break-word;
        overflow-wrap: break-word;
        overflow-x: hidden;
        max-width: 100%;
    }

    :global(.text blockquote) {
        margin: 0.5em 0;
        padding-left: 1em;
        border-left: 4px solid #444;
        color: #CCCCCC;
    }

    .input-wrapper {
        padding: 10px 20px;
        background-color: #121212;
    }

    .input-container {
        position: relative;
        background-color: #2C2C2C;
        border-radius: 20px;
        padding: 4px;
        display: flex;
        align-items: center;
        min-height: 44px;
    }

    .input-container textarea {
        flex: 1;
        background: transparent;
        border: none;
        color: #FFFFFF;
        outline: none;
        resize: none;
        overflow-y: auto;
        max-height: 100px;
        font-size: 14px;
        line-height: 1.5;
        padding: 7px 7px 10px 20px;
        margin-right: 44px;
        margin-top: 3px;
        margin-bottom: 3px;
        min-height: 36px;
        height: 36px;
        box-sizing: border-box;
    }

    .input-container textarea::placeholder {
        color: #AAAAAA;
    }

    .send-button {
        position: absolute;
        right: 8px;
        bottom: 8px;
        width: 38px;
        height: 38px;
        background-color: #0D47A1;
        border: none;
        border-radius: 50%;
        padding: 0;
        margin: 0;
        color: #FFFFFF;
        cursor: pointer;
        display: flex;
        align-items: center;
        justify-content: center;
        transition: background-color 0.2s ease;
    }

    .send-button:hover {
        background-color: #1565C0;
    }

    .send-button:disabled {
        background-color: #1E1E1E;
        cursor: default;
    }

    .send-button svg {
        width: 20px;
        height: 20px;
    }
</style>
