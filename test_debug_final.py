import asyncio
from textual.widgets import Input, ListView
from ytmtui.app import YtMTUI
from ytmtui.ytmusic import Track, YTMusicService

async def test():
    app = YtMTUI(volume=0)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        print('App mounted', flush=True)
        
        library = app.query_one('#library')
        search_results_list = library.query_one('#search-results-list')
        
        library.active_tab = 'search'
        await asyncio.sleep(0.01)
        
        from ytmtui.ytmusic import Track
        fake_tracks = [Track(id=f'test{i}', title=f'Song {i}', artist=f'Artist {i}', album='Album', duration_s=90 + i) for i in range(5)]
        
        library.set_search_results(fake_tracks)
        print('search_results:', len(library.search_results), flush=True)
        print('_search_results_list:', library._search_results_list, flush=True)
        
        # Call render_search_results with timeout
        print('Calling render_search_results...', flush=True)
        try:
            await asyncio.wait_for(library.render_search_results(), timeout=10.0)
            print('render_search_results completed', flush=True)
        except asyncio.TimeoutError:
            print('render_search_results timed out!', flush=True)
        except Exception as e:
            print(f'Error in render_search_results: {e}', flush=True)
            import traceback
            traceback.print_exc()
        
        print('Children count:', len(search_results_list.children), flush=True)

asyncio.run(test())