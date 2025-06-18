<script>
    let email = '';
    let password = '';
    let errorMessage = '';

    const handleLogin = () => {
        if (!email || !password) {
            errorMessage = 'Please fill in both fields.';
            return;
        }

        // Mock login logic
        if (email === 'user@example.com' && password === 'password123') {
            alert('Login successful!');
            // Redirect or further logic here
        } else {
            errorMessage = 'Invalid email or password.';
        }
    };
</script>

<style>
    .login-container {
        max-width: 400px;
        margin: 100px auto;
        padding: 20px;
        border-radius: 10px;
        box-shadow: 0 4px 8px rgba(0,0,0,0.1);
        background-color: white;
    }

    input {
        display: block;
        width: 100%;
        padding: 10px;
        margin: 10px 0;
        border-radius: 5px;
        border: 1px solid #ccc;
    }

    button {
        width: 100%;
        padding: 10px;
        background-color: #4CAF50;
        color: white;
        border: none;
        border-radius: 5px;
        cursor: pointer;
    }

    button:hover {
        background-color: #45a049;
    }

    .error {
        color: red;
        margin-bottom: 10px;
    }
</style>

<div class="login-container">
    <h2>Login</h2>
    {#if errorMessage}
        <div class="error">{errorMessage}</div>
    {/if}
    <input type="email" placeholder="Email" bind:value={email} />
    <input type="password" placeholder="Password" bind:value={password} />
    <button on:click={handleLogin}>Login</button>
</div>
