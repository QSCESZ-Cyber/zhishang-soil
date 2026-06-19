function gotoResetPassword() {
    const codeInput = document.querySelector('input[name="code"]');
    const code = codeInput.value.trim();
    const phone = document.querySelector('input[name="phone"]').value.trim();

    // 先简单验证验证码不为空（实际要调用后端接口验证）
    if (!code) {
        alert('请输入验证码');
        codeInput.focus();
        return;
    }

    // 验证通过后，跳转到修改密码页
    // 同时把手机号存在localStorage，方便修改密码页用
    localStorage.setItem('reset_phone', phone);
    window.location.href = '/reset_password'; // 这里填修改密码页的路由
}