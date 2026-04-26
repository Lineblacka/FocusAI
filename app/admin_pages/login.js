(function(){
      var usernameInput = document.getElementById('adminUsername');
      var passwordInput = document.getElementById('adminPassword');
      var messageBox = document.getElementById('adminLoginMessage');
      var button = document.getElementById('adminLoginButton');

      function escapeHtml(value){
        return String(value).replace(/[&<>'"]/g,function(c){return {'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[c];});
      }

      async function submitLogin(){
        var username = usernameInput.value.trim();
        var password = passwordInput.value;
        messageBox.innerHTML = '';
        if(!username || !password){
          messageBox.innerHTML = '<div class="err">Enter username and password.</div>';
          return;
        }
        button.disabled = true;
        button.textContent = 'Checking...';
        try{
          var response = await fetch('/admin/login', {
            method: 'POST',
            credentials: 'same-origin',
            headers: {'Content-Type':'application/json'},
            body: JSON.stringify({username: username, password: password})
          });
          if(!response.ok){
            var detail = 'Invalid username or password.';
            try{
              var data = await response.json();
              if(data && data.detail) detail = data.detail;
            }catch(e){}
            throw new Error(detail);
          }
          messageBox.innerHTML = '<div class="ok">Logged in. Opening dashboard...</div>';
          window.location.href = '/admin/analytics';
        }catch(error){
          messageBox.innerHTML = '<div class="err">' + escapeHtml(error.message || error) + '</div>';
        }finally{
          button.disabled = false;
          button.textContent = 'Login';
        }
      }

      button.addEventListener('click', submitLogin);
      usernameInput.addEventListener('keydown', function(event){ if(event.key === 'Enter') submitLogin(); });
      passwordInput.addEventListener('keydown', function(event){ if(event.key === 'Enter') submitLogin(); });
    })();
