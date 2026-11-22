"""Portable Windows SSH launcher. Module version is deliberately NOT embedded."""
from pathlib import Path
import argparse,base64,codecs,getpass,hashlib,locale,os,re,shlex,socket,sys,time
import paramiko

DEFAULT_PASSWORD='snapmaker'
ROOT=Path(getattr(sys,'_MEIPASS',Path(__file__).resolve().parent.parent))
TEXT={
 'ru':{'title':'U1 Companion — установка и удаление','address':'IP или имя принтера:','password':'SSH-пароль root:','agree':'Я ознакомился(лась) с GPL-3.0, отсутствием гарантий и ограничением ответственности.','install':'Установить модуль','update':'Обновить модуль','uninstall':'Удалить модуль','cancel':'Отмена','required':'Укажите адрес принтера и SSH-пароль.','fingerprint':'Первое подключение. Сверьте отпечаток SSH с вашим принтером:\n\n{fingerprint}\n\nДоверять этому принтеру?','changed':'SSH-ключ принтера изменился. Подключение остановлено.','done':'Готово. Нажмите Enter, чтобы закрыть окно.','failed':'Операция не завершена. Проверьте сообщение выше. Нажмите Enter для выхода.'},
 'en':{'title':'U1 Companion — install and uninstall','address':'Printer IP or hostname:','password':'Root SSH password:','agree':'I have read GPL-3.0, the warranty disclaimer and limitation of liability.','install':'Install module','update':'Update module','uninstall':'Uninstall module','cancel':'Cancel','required':'Enter the printer address and SSH password.','fingerprint':'First connection. Compare this SSH fingerprint with your printer:\n\n{fingerprint}\n\nTrust this printer?','changed':'The printer SSH key has changed. Connection stopped.','done':'Done. Press Enter to close.','failed':'Operation did not complete. Review the message above. Press Enter to exit.'}}


TEXT['ru'].update(changed_password='SSH-пароль меняли',prerequisite='Перед подключением включите Root Access / SSH в настройках принтера. Названия пунктов зависят от прошивки. Принтер должен быть свободен, нагрев выключен.',factory_password='Если SSH-пароль не меняли, установщик использует стандартный автоматически.',required='Укажите адрес принтера. Если SSH-пароль меняли, введите свой пароль.')
TEXT['en'].update(changed_password='I changed the SSH password',prerequisite='Before connecting, enable Root Access / SSH in the printer settings. Menu names depend on the firmware. Keep the printer idle with heaters off.',factory_password='If you have not changed the SSH password, the installer uses the factory default automatically.',required='Enter the printer address. If you changed the SSH password, enter your own password.')


def connection_password(changed,password):
    return password if changed else DEFAULT_PASSWORD


def agreement(language):
    name='AGREEMENT.ru.txt' if language=='ru' else 'AGREEMENT.en.txt'
    return (ROOT/'desktop'/name).read_text(encoding='utf-8')+'\n\n'+(ROOT/'LICENSE').read_text(encoding='utf-8')


def window():
    import tkinter as tk
    from tkinter import ttk,messagebox
    from tkinter.scrolledtext import ScrolledText
    language='ru' if (locale.getlocale()[0] or '').startswith(('ru','uk','be')) else 'en'
    root=tk.Tk();root.geometry('780x760');root.minsize(640,680);root.title('U1 Companion')
    root.iconbitmap(default=str(ROOT/'desktop/assets/u1-companion.ico'))
    frame=ttk.Frame(root,padding=14);frame.pack(fill='both',expand=True)
    lang=tk.StringVar(value=language);host=tk.StringVar();password=tk.StringVar();accepted=tk.BooleanVar(value=False);changed_password=tk.BooleanVar(value=False);result={}
    chooser=ttk.Combobox(frame,textvariable=lang,values=['ru','en'],state='readonly',width=6);chooser.pack(anchor='e')
    logo=tk.PhotoImage(file=str(ROOT/'desktop/assets/u1-companion-64.png'))
    heading=ttk.Label(frame,font=('',15,'bold'),image=logo,compound='left',padding=(0,0,8,0));heading.pack(anchor='w',pady=(0,8))
    terms=ScrolledText(frame,wrap='word',height=17,font=('Segoe UI',10));terms.pack(fill='both',expand=True)
    prerequisite=ttk.Label(frame,wraplength=580);prerequisite.pack(fill='x',pady=(10,0))
    fields=ttk.Frame(frame);fields.pack(fill='x',pady=10);fields.columnconfigure(1,weight=1)
    address_label=ttk.Label(fields);address_label.grid(row=0,column=0,sticky='w',padx=(0,8),pady=4)
    address=ttk.Entry(fields,textvariable=host);address.grid(row=0,column=1,sticky='ew',pady=4)
    changed_checkbox=ttk.Checkbutton(fields,variable=changed_password);changed_checkbox.grid(row=1,column=0,columnspan=2,sticky='w',pady=4)
    password_label=ttk.Label(fields);password_label.grid(row=2,column=0,sticky='w',padx=(0,8),pady=4)
    password_entry=ttk.Entry(fields,textvariable=password,show='*');password_entry.grid(row=2,column=1,sticky='ew',pady=4)
    factory_hint=ttk.Label(fields,wraplength=580);factory_hint.grid(row=3,column=0,columnspan=2,sticky='w',pady=4)
    def toggle_password(*_):
        if changed_password.get():
            password_label.grid();password_entry.grid();factory_hint.grid_remove();password_entry.focus_set()
        else:
            password.set('');password_label.grid_remove();password_entry.grid_remove();factory_hint.grid()
    changed_password.trace_add('write',toggle_password)
    checkbox=ttk.Checkbutton(frame,variable=accepted);checkbox.pack(anchor='w',pady=6)
    actions=ttk.Frame(frame);actions.pack(fill='x',pady=(8,0));buttons={}
    def choose(action):
        text=TEXT[lang.get()]
        if not accepted.get():return
        h=host.get().strip()
        credential=connection_password(changed_password.get(),password.get())
        if not h or not re.fullmatch(r'[A-Za-z0-9.:-]{1,253}',h) or not credential:
            messagebox.showerror('U1 Companion',text['required'],parent=root);return
        result.update(host=h,password=credential,action=action,language=lang.get());password.set('');root.destroy()
    for action in ['install','update','uninstall']:
        buttons[action]=ttk.Button(actions,command=lambda a=action:choose(a));buttons[action].pack(side='left',padx=(0,8),fill='x',expand=True)
    cancel=ttk.Button(actions,command=root.destroy);cancel.pack(side='right')
    def refresh(*_):
        text=TEXT[lang.get()];root.title(text['title']);heading.config(text=text['title'])
        terms.config(state='normal');terms.delete('1.0','end');terms.insert('1.0',agreement(lang.get()));terms.config(state='disabled')
        address_label.config(text=text['address']);password_label.config(text=text['password']);checkbox.config(text=text['agree'])
        prerequisite.config(text=text['prerequisite']);changed_checkbox.config(text=text['changed_password']);factory_hint.config(text=text['factory_password'])
        for action,button in buttons.items():button.config(text=text[action],state='normal' if accepted.get() else 'disabled')
        cancel.config(text=text['cancel'])
    lang.trace_add('write',lambda *_:(accepted.set(False),refresh()));accepted.trace_add('write',lambda *_:[b.config(state='normal' if accepted.get() else 'disabled') for b in buttons.values()])
    refresh();toggle_password();address.focus_set();root.mainloop();return result


def verify_host(host,key,ask,path=None):
    path=path or Path(os.environ.get('LOCALAPPDATA',str(Path.home())))/'U1Companion/known_hosts'
    for part in (path,*path.parents):
        if part.is_symlink():raise ValueError('Unexpected known_hosts symlink')
    keys=paramiko.HostKeys()
    if path.exists():keys.load(str(path))
    existing=keys.lookup(host)
    if existing:
        if not keys.check(host,key):raise ValueError('SSH_HOST_KEY_CHANGED')
    else:
        fingerprint='SHA256:'+base64.b64encode(hashlib.sha256(key.asbytes()).digest()).decode().rstrip('=')
        if not ask(fingerprint):raise ValueError('Connection cancelled')
        keys.add(host,key.get_name(),key)
    return keys,path


def remote_command(action):
    if action not in ('install','update','uninstall'):raise ValueError('Unknown action')
    from bootstrap import CODE
    code=CODE
    return 'python3 -c '+shlex.quote(code)+' && sh /userdata/u1-companion-install.sh --'+action


def execute(options):
    from tkinter import Tk,messagebox
    text=TEXT[options['language']];transport=None
    try:
        print('U1 Companion — '+text[options['action']],flush=True)
        print('Keep this window open until the operation finishes.\n',flush=True)
        transport=paramiko.Transport(socket.create_connection((options['host'],22),timeout=15));transport.start_client(timeout=20)
        def ask(fingerprint):
            prompt=Tk();prompt.withdraw()
            try:return messagebox.askyesno('U1 Companion',text['fingerprint'].format(fingerprint=fingerprint),parent=prompt)
            finally:prompt.destroy()
        try:keys,path=verify_host(options['host'],transport.get_remote_server_key(),ask)
        except ValueError as error:
            if str(error)=='SSH_HOST_KEY_CHANGED':raise ValueError(text['changed'])
            raise
        transport.auth_password('root',options['password']);options['password']=''
        path.parent.mkdir(parents=True,exist_ok=True);temp=path.with_suffix('.next');keys.save(str(temp));os.replace(temp,path)
        channel=transport.open_session(timeout=20);channel.get_pty(term='xterm',width=100,height=30);channel.exec_command(remote_command(options['action']))
        decoder=codecs.getincrementaldecoder('utf-8')('replace')
        import msvcrt
        while True:
            if channel.recv_ready():sys.stdout.write(decoder.decode(channel.recv(16384)));sys.stdout.flush()
            elif channel.exit_status_ready():break
            if msvcrt.kbhit():
                ch=msvcrt.getwch()
                if ch in ('\x00','\xe0'):msvcrt.getwch();continue
                if ch=='\x03':raise KeyboardInterrupt()
                channel.sendall(('\n' if ch=='\r' else '\x7f' if ch=='\b' else ch).encode())
            time.sleep(.03)
        status=channel.recv_exit_status();print('\n'+(text['done'] if status==0 else text['failed']));return status
    finally:
        options['password']=''
        if transport:transport.close()


def main():
    parser=argparse.ArgumentParser(description='Universal U1 Companion installer/uninstaller; no module version is embedded.')
    parser.add_argument('--self-test',action='store_true',help='Check bundled imports and license files; no UI acceptance or network activity')
    args=parser.parse_args()
    if args.self_test:
        import tkinter,cryptography
        assert connection_password(False,'ignored')==DEFAULT_PASSWORD
        assert connection_password(True,'custom')=='custom' and connection_password(True,'')==''
        assert (ROOT/'desktop/assets/u1-companion.ico').is_file() and (ROOT/'desktop/assets/u1-companion-64.png').is_file()
        assert 'GNU GENERAL PUBLIC LICENSE' in agreement('en')
        assert '--uninstall' in remote_command('uninstall') and '/releases/latest' in remote_command('update')
        print('SELF-TEST OK: SSH, Tk, licenses; no printer connection');return 0
    options=window()
    if not options:return 0
    try:status=execute(options)
    except (Exception,KeyboardInterrupt) as error:
        print('\nERROR:',type(error).__name__,str(error));status=1
    input('\nEnter / Ввод: ');return status


if __name__=='__main__':sys.exit(main())
