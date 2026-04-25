from app.main import create_app


def run_cli() -> None:
    app = create_app()
    memory_store = app.state.memory_store
    ai_service = app.state.ai_service
    quality_service = app.state.quality_service
    command_service = app.state.command_service

    print('FocusAI стартира')
    print("Напиши /help за команди или 'exit' за край.\n")

    while True:
        user_input = input('Ти: ').strip()
        if not user_input:
            continue
        if user_input.lower() in {'exit', 'quit', 'край'}:
            print('FocusAI: Добре. Но утре пак имаш работа.')
            break
        if user_input.startswith('/'):
            result = command_service.handle(user_input)
            print(f"FocusAI: {result['message']}")
            if result.get('data'):
                print(result['data'])
            continue

        memory = memory_store.load_session('cli')
        _, messages = ai_service.build_messages(memory, user_input)
        result = ai_service.ask(messages)
        reply = quality_service.clean_output(result['content'])
        quality = quality_service.check(reply)
        if not quality['passed']:
            print(f"Quality warning: {quality['issues']}")
        print(f'\nFocusAI: {reply}\n')
        memory_store.append_turn(user_input, reply, result.get('model'), result.get('latency_seconds'), 'cli')


if __name__ == '__main__':
    run_cli()
