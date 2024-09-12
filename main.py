from argparse import ArgumentParser
from pprint import pformat
from string import printable, digits, ascii_letters
from requests import get, post, RequestException

class MissingTargetUrl(Exception):
    pass

class MissingVideoData(Exception):
    pass

class Video:
    def __init__(self, id, key, size="??? MB", quality='none'):
        self.id = id
        self.key = key
        self.size = size
        self.quality = quality

    def __str__(self) -> str:
        return "Video {{ id: {id}, key: {key}, size: {size}, quality: {quality} }}".format(id=self.id,
                                                                                   key=self.key,
                                                                                   size=self.size,
                                                                                   quality=self.quality,
                                                                                   )
    def __repr__(self) -> str:
        return self.__str__()

class YTDownloader:
    __host = "https://www.y2mate.com"
    __analyze_endpoint = "/mates/analyzeV2/ajax"
    __analyze_query_parameter = "k_query={}"
    __convert_endpoint =  "/mates/convertV2/index"
    __convert_query_parameter = "vid={}&k={}"
    __default_headers = {"Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
                         "Referer": "https://www.y2mate.com/",
                         }
    __url_error = "error: url inválida -> {}"
    __missing_target_url = "error: no hay url objetivo"
    __missing_data_error = "error: los datos del vídeo no existen"
    __connection_error = "error: compruebe su conexión a internet o cortafuegos"
    __quality_value_error = "error: valor de calidad incorecto -> {}"
    __quality_not_existent_error = "error: calidad no disponible -> {}p"

    def __init__(self):
        self.__target = ''
        self.__data = {}
  
    def __check_data(self) -> int:
        if self.__data == {}:
            return 1
        return 0
    
    def __check_target(self) -> int:
        if self.__target == '':
            return 1
        return 0

    def __reset_data(self) -> None:
        self.__data = {}

    def __verify_url(self, url:str) -> int:
        p = "https://www.youtube.com", "https://youtube.com", "https://youtu.be"
        if not url.startswith("https://"):
            url = "https://" + url
        if any([url.startswith(i) for i in p]):
            return 0
        return 1

    def set_target(self, url:str) -> None:
        if self.__verify_url(url) != 0:
            raise ValueError(self.__url_error.format(url))
        self.__target = url
    
    def reset_target(self) -> None:
        self.__target = ''
        self.__reset_data()

    def get_info(self):
        if self.__check_target() != 0:
            raise MissingTargetUrl(self.__missing_target_url)
        try:
            info = self.__analyze(self.__target)
        except RequestException:
            raise RequestException(self.__connection_error)
        return self.__save_info(info)

    def __check_quality(self, quality, allow_lt:bool=False) -> Video:
        if self.__check_data() != 0:
            raise MissingVideoData(self.__missing_data_error)
        raise_err = 0
        if isinstance(quality, str):
            quality = quality.strip()
            if not (quality[-1] == 'p' or quality[-1].isnumeric()):
                raise_err = 1
            else:
                try:
                    quality = int(quality.strip(printable.replace(digits, '')))
                except ValueError:
                    raise_err = 1
            if raise_err:
                raise ValueError(self.__quality_value_error.format(quality))
        if isinstance(quality, int):
            if allow_lt:
                matching_qualities = tuple(filter(lambda key_qual: quality >= key_qual, self.__data["qualities"].keys()))
                if matching_qualities:
                    quality = max(matching_qualities)
                else:
                    raise_err = 1
            try:
                video = self.__data["qualities"][quality]
            except KeyError:
                raise_err = 1
            if raise_err:
                raise KeyError(self.__quality_not_existent_error.format(quality))
        else:
            raise ValueError(self.__quality_value_error.format(quality))
        return video

    def download(self, calidad, allow_lt:bool=False) -> int:        
        video = self.__check_quality(calidad, allow_lt)
        self.__download(video)
        self.reset_target()
        return 0

    def __download(self, video:Video) -> int:
        link = self.__get_download_link(video)
        try:
            response = get(link,
                           stream=True)
        except RequestException:
            raise RequestException("error: error al descargar el video. compruebe su conexión a internet o su cortafuegos")
        def update_bar(done, target, length_bar):
            p = done / target
            buffer = '['
            asterisc = round(length_bar*p)
            buffer += '*'*asterisc + '-'*(length_bar - asterisc)
            buffer += '] {} % ({} MB / {} MB)'.format(round(p*100),
                                                      round(done / 1000000, 3),
                                                      round(target / 1000000, 3),
                                                      )
            return buffer

        video_title = self.get_video_name()
        LENGTH_BAR = 50
        CHUNK_SIZE = 1024
        iterator = response.iter_content(CHUNK_SIZE)
        downloaded = 0
        target_size = int(response.headers["Content-Length"].strip())
        last_bar_lenght = 0
        try:
            with open(video_title+".mp4", "wb") as file:
                print("Downloading video: {}.mp4 ({})".format(video_title, video.quality))
                for chunk in iterator:
                    file.write(chunk)
                    downloaded += len(chunk)
                    bar = update_bar(downloaded, target_size, LENGTH_BAR)
                    print('\r' + ' '*last_bar_lenght + '\r' + bar, end='')
                    last_bar_lenght = len(bar)
        except PermissionError:
            raise PermissionError("error: no se pudo crear el archivo debido a falta de permisos")
        except OSError as e:
            if e.strerror == "Invalid argument":
                raise OSError("error: no se pudo crear el archivo: título inválido: {}".format(video_title))
            raise e
        print("\nFinished! -> {}.mp4".format(video_title))
        return 0

    def get_video_name(self) -> str:
        try:
            return ''.join(list(map(lambda x: x if x not in "<>:\"/\\|?*" else '_', self.__data["title"])))
        except KeyError:
            raise MissingVideoData(self.__missing_data_error)
    
    def __save_info(self, info:dict) -> int:
        strip_stuff = lambda x: x.strip(printable.replace(digits, ''))
        if "links" in info.keys() and "mp4" in info["links"]:
            self.__data["title"] = info["title"]
            self.__data["vid"] = info["vid"]
            self.__data["qualities"] = {}
            for quality_data in info["links"]["mp4"].values():
                if quality_data["q"] != "auto" and quality_data["f"] == "mp4":
                    index = int(strip_stuff(quality_data["q"]))
                    self.__data["qualities"][index] = Video(info["vid"],
                                                            quality_data["k"],
                                                            quality_data["size"] if quality_data["size"][0].isnumeric() else "??? MB",
                                                            quality_data["q"],
                                                            )
            return 0
        else:
            raise MissingVideoData(self.__missing_data_error)

    def __analyze(self, url:str) -> dict:
        r = post(self.__host + self.__analyze_endpoint,
                 headers=self.__default_headers,
                 data=self.__analyze_query_parameter.format(url_encode(url)))
        return r.json()

    def __convert(self, video:Video) -> dict:
        '''Le pregunta a la API por el link de descarga del video ingresado como parámetro'''
        r = post(self.__host + self.__convert_endpoint,
                 headers=self.__default_headers,
                 data=self.__convert_query_parameter.format(video.id, url_encode(video.key))
                 )
        return r.json()

    def __get_download_link(self, video:Video):
        try:
            data = self.__convert(video)
            dlink = data["dlink"]
        except KeyError:
            raise KeyError("error: error al obtener el link de descarga")
        except RequestException:
            raise RequestException(self.__connection_error)
        return dlink.replace("\\/", "/")

    def get_formatted_data(self, print_:bool=True) -> str:
        if not self.__check_data():
            raise MissingVideoData(self.__missing_data_error)
        d = pformat(self.__data)
        if print_:
            print(d)
        return d

    def print_available_qualities(self, add_choices:bool=False) -> tuple:
        if self.__check_data() != 0:
            raise MissingVideoData(self.__missing_data_error)
        qualities = self.__data["qualities"]
        list_of_qualities = list(qualities.keys())
        list_of_qualities.sort(reverse=True)
        print("{} de video disponible para descargar:".format("Calidades" if len(list_of_qualities) > 1 else "Calidad"))
        for pos, key in enumerate(list_of_qualities):
            print("{}{} -> {}".format("[{}] - ".format(pos+1) if add_choices else '', str(key)+'p', qualities[key].size))
        return tuple(list_of_qualities)

def url_encode(string:str):
    return ''.join(list(map(lambda x: x if x in ascii_letters+digits else '%'+x.encode('utf-8').hex().upper(), string)))

if __name__ == "__main__":
    parser = ArgumentParser()
    parser.add_argument("link", nargs="?", default='',
                        help="el link del vídeo que quieres descargar")
    parser.add_argument("calidad", nargs="?", default='',
                        help="la calidad en la que prefieres descargar el vídeo")
    parser.add_argument("--stdin", action="store_true",
                        help="flag para ingresar tanto la url como la calidad por la entrada de datos estándar (stdin)")
    parser.add_argument("--exact", action="store_true",
                        help="flag para descargar exactamente la calidad ingresada "
                        "(por defecto: aceptar calidad menor o igual a la introducida)")
    args = parser.parse_args()

    downloader = YTDownloader()

    if args.stdin:
        if args.link:
            parser.error("argument --stdin: not allowed with argument link or calidad")
        link = input("Ingrese el link: ").strip()
    elif args.link:
        link = args.link
    else:
        parser.print_help()
        exit(1)

    try:
        downloader.set_target(link)
    except ValueError as e:
        print(e.args[0])
        exit(1)

    try:
        downloader.get_info()
    except Exception as e:
        print(e.args[0])
        exit(1)

    try:
        print("Link de vídeo detectado! -> {}".format(downloader.get_video_name()))
    except (KeyError, MissingVideoData) as e:
        print(e.args[0])
        exit(1)

    if args.stdin:
        try:
            ammount_qualities = downloader.print_available_qualities(True)
        except Exception as e:
            print(e.args[0])
            exit(1)
        calidad = input("-> ").strip()
        try:
            number = int(calidad)
            if not (number > 0 and number <= len(ammount_qualities)):
                raise ValueError()
        except ValueError:
            print("Opción inválida")
            exit(1)
        calidad = ammount_qualities[number]
    else:
        if not args.calidad:
            downloader.print_available_qualities()
            exit(1)
        else:
            calidad = args.calidad

    code = 0
    try:
        downloader.download(calidad, not args.exact)
    except KeyboardInterrupt:
        pass
    except (KeyError, ValueError, RequestException, MissingVideoData, PermissionError, OSError) as e:
        print(' '.join(e.args))
        code = 1
    except BaseException as e:
        if isinstance(e, SystemExit):
            exit(e.code)
        print("error: " + ' '.join(e.args))
        code = 1

    exit(code)
